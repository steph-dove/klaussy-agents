"""A check that can't run must not read as a check that failed.

Regression coverage for the bug where a `klaussy` older than the guard exited 2
on an unknown subcommand ("No such command 'import-lint'") and the guard read
that as findings, blocking every commit. Both guard templates share the logic,
so each test runs against both.
"""

import contextlib
import importlib.util
import io
import json
from importlib import resources

import pytest

GUARD_TEMPLATES = ["git_commit_guard.py", "multi/commit_guard.py"]

# The Claude guard gates on Claude's event/tool fields; the cross-agent one
# reads whatever shape its agent sends. One payload each, same command.
PAYLOADS = {
    "git_commit_guard.py": {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'feat: x'"},
    },
    "multi/commit_guard.py": {"tool_input": {"command": "git commit -m 'feat: x'"}},
}


def _load_guard(relpath: str):
    path = resources.files("klaussy").joinpath(f"templates/hooks/{relpath}")
    mod_name = "klaussy_usage_guard_" + relpath.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(params=GUARD_TEMPLATES)
def guard(request, monkeypatch):
    mod = _load_guard(request.param)
    mod._payload_for_test = PAYLOADS[request.param]
    # Stand in for a real commit: one staged file, so every check resolves.
    monkeypatch.setattr(mod, "_changed_paths", lambda include_unstaged=False: ["a.py"])
    return mod


def _run_guard(guard, monkeypatch, rc: int) -> tuple[int, str]:
    """Drive main() with every check exiting `rc`; return (exit code, stderr)."""
    monkeypatch.setattr(guard, "_run", lambda cmd: rc)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(guard._payload_for_test)))
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = guard.main()
    return code, err.getvalue()


def test_usage_error_allows_the_commit(guard, monkeypatch):
    code, _ = _run_guard(guard, monkeypatch, guard.USAGE_EXIT)
    assert code == 0, "a check that couldn't run must not block the commit"


def test_usage_error_says_the_check_was_skipped(guard, monkeypatch):
    """Silence here would look identical to a clean pass — including for secrets."""
    _, err = _run_guard(guard, monkeypatch, guard.USAGE_EXIT)
    assert "SKIPPED" in err
    assert "not passed" in err


def test_usage_error_names_the_check(guard, monkeypatch):
    _, err = _run_guard(guard, monkeypatch, guard.USAGE_EXIT)
    assert "klaussy secret-scan" in err, f"should name the check that skipped, got: {err!r}"


def test_findings_still_block(guard, monkeypatch):
    code, err = _run_guard(guard, monkeypatch, 1)
    assert code == 2, "exit 1 is findings — that must still block"
    assert "reported problems" in err


def test_clean_check_is_silent(guard, monkeypatch):
    code, err = _run_guard(guard, monkeypatch, 0)
    assert code == 0
    assert err == "", "a passing gate should say nothing"


@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("klaussy import-lint --diff a.py", "klaussy import-lint"),
        ("klaussy secret-scan --diff a.py b.py", "klaussy secret-scan"),
        ("ruff check --fix a.py", "ruff check"),
        ("ruff format a.py", "ruff format"),
        ("npx eslint --fix a.js", "npx eslint"),
    ],
)
def test_check_name_reads_as_the_command(guard, cmd, expected):
    assert guard._check_name(cmd) == expected


def test_check_name_survives_an_unparseable_command(guard):
    assert guard._check_name('klaussy comment-lint --diff "unclosed') == "a check"
