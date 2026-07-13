"""The self-review stop hook: correct per-agent output, loop-safe, diff-gated."""

import importlib.util
import json
import subprocess
from importlib import resources

import pytest


def _load_guard():
    path = resources.files("klaussy").joinpath("templates/hooks/multi/self_review_guard.py")
    spec = importlib.util.spec_from_file_location("klaussy_self_review_guard", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def guard():
    return _load_guard()


# --- per-agent output dialect ----------------------------------------------


@pytest.mark.parametrize("dialect", ["claude", "codex", "copilot"])
def test_decision_block_dialects(guard, dialect):
    out = guard._emit(dialect)
    assert out["decision"] == "block" and out["reason"]


def test_gemini_uses_deny(guard):
    out = guard._emit("gemini")
    assert out["decision"] == "deny" and out["reason"]


def test_cursor_uses_followup_message(guard):
    out = guard._emit("cursor")
    assert out == {"followup_message": guard.DIRECTIVE}


def test_unknown_dialect_emits_nothing(guard):
    assert guard._emit("cline") is None  # observe-only, not wired


# --- native loop guard ------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"stop_hook_active": True}, True),
        ({"loop_count": 1}, True),
        ({"loop_count": 0}, False),
        ({"stop_hook_active": False}, False),
        ({}, False),
    ],
)
def test_native_loop_allow(guard, payload, expected):
    assert guard._native_loop_allow(payload) is expected


def test_session_id_extraction(guard):
    assert guard._session_id({"sessionId": "abc"}) == "abc"
    assert guard._session_id({"conversation_id": "z"}) == "z"
    assert guard._session_id({}) == "nosession"


# --- end-to-end against a real repo ----------------------------------------


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, capture_output=True)


def _run_guard(guard_path, repo, payload):
    r = subprocess.run(
        ["python3", str(guard_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=repo,
    )
    return r.returncode, r.stdout.strip()


def test_guard_blocks_on_uncommitted_code_then_marker_allows(tmp_path):
    from klaussy import hooks

    repo = tmp_path
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    hooks._install_self_review_guard_script(repo, "claude")
    guard_path = repo / ".claude" / "hooks" / "self_review_guard.py"
    session = {"hook_event_name": "Stop", "session_id": f"s-{tmp_path.name}"}

    # Clean tree: nothing to review -> allow (no output).
    assert _run_guard(guard_path, repo, session) == (0, "")

    # Uncommitted code change -> block once with a reason.
    (repo / "a.py").write_text("x = 2\n")
    rc, out = _run_guard(guard_path, repo, session)
    assert rc == 0
    assert json.loads(out) == {"decision": "block", "reason": _load_guard().DIRECTIVE}

    # Same session + HEAD again -> marker guard allows (loop-safe).
    assert _run_guard(guard_path, repo, session) == (0, "")


def test_guard_ignores_non_code_changes(tmp_path):
    from klaussy import hooks

    repo = tmp_path
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("# hi\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    hooks._install_self_review_guard_script(repo, "claude")
    guard_path = repo / ".claude" / "hooks" / "self_review_guard.py"

    # A docs-only change must not trigger the nudge.
    (repo / "README.md").write_text("# hi there\n")
    assert _run_guard(guard_path, repo, {"session_id": f"d-{tmp_path.name}"}) == (0, "")
