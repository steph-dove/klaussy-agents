"""The commit guard must hand each tool only the file types it understands.

Regression coverage for the bug where every staged path was passed to `ruff`,
so a `.md`/`.json`/`.toml` committed alongside Python made ruff fail to parse it
and wrongly block the commit. Both guard templates (Claude `git_commit_guard.py`
and the cross-agent `multi/commit_guard.py`) share the filtering logic, so each
test runs against both.
"""

import importlib.util
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
