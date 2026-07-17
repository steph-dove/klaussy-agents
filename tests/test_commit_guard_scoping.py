"""The commit guard must hand each tool only the file types it understands.

Regression coverage for the bug where every staged path was passed to `ruff`,
so a `.md`/`.json`/`.toml` committed alongside Python made ruff fail to parse it
and wrongly block the commit. Both guard templates (Claude `git_commit_guard.py`
and the cross-agent `multi/commit_guard.py`) share the filtering logic, so each
test runs against both.
"""

import contextlib
import importlib.util
import io
import json
from importlib import resources

import pytest

GUARD_TEMPLATES = ["git_commit_guard.py", "multi/commit_guard.py"]


def _load_guard(relpath: str):
    path = resources.files("klaussy").joinpath(f"templates/hooks/{relpath}")
    mod_name = "klaussy_guard_" + relpath.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(params=GUARD_TEMPLATES)
def guard(request):
    return _load_guard(request.param)


# --- tool sniffing ---------------------------------------------------------


def test_command_tool_bare(guard):
    assert guard._command_tool("ruff format x.py") == "ruff"


def test_command_tool_skips_npx(guard):
    assert guard._command_tool("npx eslint --fix x.js") == "eslint"


def test_command_tool_skips_uv_run(guard):
    assert guard._command_tool("uv run ruff check --fix __KLAUSSY_PATHS__") == "ruff"


def test_command_tool_basenames_path(guard):
    assert guard._command_tool("/usr/bin/ruff format x.py") == "ruff"


def test_command_tool_unknown_runner_only(guard):
    # A command that is nothing but flags/runners has no tool to sniff.
    assert guard._command_tool("npx --yes") is None


# --- path filtering --------------------------------------------------------


def test_ruff_drops_non_python_paths(guard):
    paths = ["src/app.py", "README.md", "pyproject.toml", "data.json", "lib.pyi"]
    assert guard._applicable_paths("ruff format __KLAUSSY_PATHS__", paths) == [
        "src/app.py",
        "lib.pyi",
    ]


def test_eslint_keeps_only_js_like(guard):
    paths = ["a.ts", "b.tsx", "c.py", "d.css", "e.js"]
    assert guard._applicable_paths("npx eslint --fix __KLAUSSY_PATHS__", paths) == [
        "a.ts",
        "b.tsx",
        "e.js",
    ]


def test_unknown_tool_keeps_all_paths(guard):
    # prettier self-filters via --ignore-unknown; comment-lint filters internally.
    paths = ["a.md", "b.json", "c.yaml"]
    cmd = "npx prettier --write --ignore-unknown __KLAUSSY_PATHS__"
    assert guard._applicable_paths(cmd, paths) == paths
    assert guard._applicable_paths("klaussy comment-lint --diff __KLAUSSY_PATHS__", paths) == paths


# --- resolve: the behavior the guard actually relies on --------------------


def test_resolve_scopes_ruff_to_python(guard):
    resolved = guard._resolve("ruff format __KLAUSSY_PATHS__", ["app.py", "README.md"])
    assert resolved == "ruff format app.py"


def test_resolve_skips_ruff_when_no_python_staged(guard):
    # The reported bug: a docs-only commit must NOT invoke ruff at all.
    assert guard._resolve("ruff format __KLAUSSY_PATHS__", ["README.md", "x.json"]) is None


def test_resolve_quotes_paths_with_spaces(guard):
    resolved = guard._resolve("ruff check __KLAUSSY_PATHS__", ["my dir/app.py"])
    assert resolved == "ruff check 'my dir/app.py'"


def test_resolve_passes_through_command_without_token(guard):
    assert guard._resolve("ruff check .", ["app.py"]) == "ruff check ."


# --- --no-verify is honored ------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m wip",
        "git commit -n -m wip",
        "git commit -anm wip",  # combined short flags: -a -n -m
        "git -C sub commit --no-verify",
    ],
)
def test_skips_verify_true(guard, command):
    assert guard._skips_verify(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m wip",
        "git commit -am wip",  # -a -m, no -n
        "git commit --no-edit",  # different long flag that isn't --no-verify
        'git commit -m "fix -n in parser"',  # 'n' lives in the message, not a flag
    ],
)
def test_skips_verify_false(guard, command):
    assert guard._skips_verify(command) is False


# --- block message stays terse (no context flood) --------------------------


def test_blocked_message_is_concise(guard):
    # The resolved command can carry hundreds of staged paths; the block notice
    # must not echo them back (that repetition is what floods an agent's context).
    resolved = "ruff check --fix " + " ".join(f"file{i}.py" for i in range(200))
    msg = guard._blocked_message(resolved)
    assert "ruff" in msg
    assert "--no-verify" in msg
    assert "file0.py" not in msg
    assert msg.count("\n") == 0


def test_blocked_message_handles_unknown_tool(guard):
    msg = guard._blocked_message("klaussy comment-lint --diff a.py")
    assert "--no-verify" in msg
    assert "a.py" not in msg


# --- conventional-commit message extraction --------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m 'feat: x'", ["feat: x"]),
        ("git commit -mfeat: x", ["feat:"]),  # attached value stops at the space
        ("git commit --message 'fix: y'", ["fix: y"]),
        ("git commit --message=fix:y", ["fix:y"]),
        ("git commit -am 'chore: z'", ["chore: z"]),  # combined -a -m, value next token
        ("git commit -m 'feat: a' -m body", ["feat: a", "body"]),  # subject is first
        ("git commit --amend", []),  # editor commit: no inline message
        ("git commit", []),
    ],
)
def test_commit_messages_extraction(guard, command, expected):
    assert guard._commit_messages(command) == expected


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add thing",
        "fix(parser): handle empty input",
        "refactor!: drop legacy path",
        "docs: update readme",
        "chore(deps): bump ruff",
    ],
)
def test_conventional_re_accepts(guard, subject):
    assert guard.CONVENTIONAL_RE.match(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "add thing",  # no type
        "feat add thing",  # missing colon
        "feature: add thing",  # not an allowed type
        "Fix: add thing",  # wrong case
        "feat:",  # empty subject
    ],
)
def test_conventional_re_rejects(guard, subject):
    assert guard.CONVENTIONAL_RE.match(subject) is None


def test_bad_commit_message_notice_is_actionable(guard):
    msg = guard._bad_commit_message("add thing")
    assert "Conventional Commits" in msg
    assert "--no-verify" in msg
    assert "add thing" in msg  # echoes the offending subject


# --- _run resolves the executable via PATH (Windows .cmd/.exe safety) -------


def test_run_missing_tool_allows(guard, monkeypatch):
    # An uninstalled tool can't judge the diff, so the commit is allowed silently
    # (previously via a caught FileNotFoundError; now via an explicit which miss).
    monkeypatch.setattr(guard.shutil, "which", lambda _name: None)
    assert guard._run("definitely-not-a-real-tool --fix x.py") == 0


def test_run_resolves_executable_and_returns_code(guard, monkeypatch):
    seen = {}

    def fake_run(argv, *a, **k):
        seen["argv"] = argv
        return type("R", (), {"returncode": 7})()

    monkeypatch.setattr(guard.shutil, "which", lambda name: "/opt/tools/" + name)
    monkeypatch.setattr(guard.subprocess, "run", fake_run)
    assert guard._run("ruff format x.py") == 7
    # The bare name is replaced by the PATH-resolved path before running.
    assert seen["argv"] == ["/opt/tools/ruff", "format", "x.py"]


def test_run_wraps_windows_cmd_shim(guard, monkeypatch):
    # On Windows a Node entrypoint resolves to a .cmd shim, which CreateProcess
    # can't launch directly — it must go through cmd.exe.
    seen = {}

    def fake_run(argv, *a, **k):
        seen["argv"] = argv
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(guard.sys, "platform", "win32")
    monkeypatch.setattr(guard.shutil, "which", lambda name: "C:\\tools\\" + name + ".cmd")
    monkeypatch.setattr(guard.subprocess, "run", fake_run)
    assert guard._run("npx eslint --fix x.js") == 0
    assert seen["argv"][:2] == ["cmd", "/c"]
    assert seen["argv"][2] == "C:\\tools\\npx.cmd"
    assert seen["argv"][3:] == ["eslint", "--fix", "x.js"]


# --- staging detection ----------------------------------------------------


@pytest.mark.parametrize(
    "command, expected",
    [
        ("git add -A && git commit -m 'feat: x'", True),
        ("git add . && git commit -m 'feat: x'", True),
        ("git add src/a.py && git commit -m 'feat: x'", True),
        ("git -C /repo add -A && git commit -m 'feat: x'", True),
        ("git add -A; git commit -m 'feat: x'", True),
        ("git commit -m 'feat: x'", False),
        ("git commit -m 'feat: add support'", False),
        ("git log --grep=add", False),
    ],
)
def test_stages_files_detects_add_on_the_same_line(guard, command, expected):
    assert guard._stages_files(command) is expected


def _drive_main(guard, monkeypatch, command: str) -> list[bool]:
    """Run main() on `command`; return the include_unstaged it asked _changed_paths for."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    asked: list[bool] = []

    def fake_changed_paths(include_unstaged):
        asked.append(include_unstaged)
        return ["a.py"]

    monkeypatch.setattr(guard, "_changed_paths", fake_changed_paths)
    monkeypatch.setattr(guard, "_run", lambda cmd: 0)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    with contextlib.redirect_stderr(io.StringIO()):
        guard.main()
    return asked


@pytest.mark.parametrize(
    "command, include_unstaged",
    [
        # Regression: `git add -A && git commit` fires this hook before the add
        # runs, so a --cached-only lookup saw zero paths and silently skipped
        # every check — the commit went through unjudged.
        ("git add -A && git commit -m 'feat: x'", True),
        ("git commit -am 'feat: x'", True),
        # No add on the line, so the index is authoritative — unrelated working
        # tree edits must not be dragged into the gate and block the commit.
        ("git commit -m 'feat: x'", False),
    ],
)
def test_main_widens_to_working_tree_only_when_staging_is_pending(
    guard, monkeypatch, command, include_unstaged
):
    assert _drive_main(guard, monkeypatch, command) == [include_unstaged]
