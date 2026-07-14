"""Tests for the comment-humanizing guards (Claude rewrite + cross-agent block)."""

import importlib.util
import io
import json
import shlex
from pathlib import Path

import pytest

from klaussy import hooks as hooks_mod

TEMPLATES = Path(hooks_mod.__file__).parent / "templates" / "hooks"


def _load(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, TEMPLATES / relpath)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def claude():
    return _load("comment_guard.py", "_claude_comment_guard")


@pytest.fixture()
def multi():
    return _load("multi/comment_guard.py", "_multi_comment_guard")


# --- shared detection / parsing -------------------------------------------


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_detects_comment_posts(mod_name, claude, multi):
    mod = {"claude": claude, "multi": multi}[mod_name]
    assert mod._is_comment_post('gh pr comment 1 --body "hi"')
    assert mod._is_comment_post('gh issue comment 2 -b "hi"')
    assert mod._is_comment_post('gh pr review --comment --body "hi"')
    assert not mod._is_comment_post('git commit -m "x"')
    assert not mod._is_comment_post("gh pr view 1")


def test_find_body_forms(claude):
    assert claude._find_body(shlex.split('gh pr comment 1 -b "hello"'))[1] == "hello"
    assert claude._find_body(shlex.split('gh pr comment 1 --body "hello"'))[1] == "hello"
    idx, body, inline = claude._find_body(shlex.split("gh pr comment 1 --body=hello"))
    assert body == "hello" and inline is True
    assert claude._find_body(shlex.split("gh pr comment 1")) is None


# --- Claude: transparent rewrite via updatedInput -------------------------


def _feed(mod, monkeypatch, command, event="PreToolUse", tool="Bash"):
    payload = {"hook_event_name": event, "tool_name": tool, "tool_input": {"command": command}}
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))


def test_claude_rewrites_with_humanized_body(claude, monkeypatch, capsys):
    monkeypatch.setattr(claude, "_humanize", lambda t: "Clean version.")
    _feed(claude, monkeypatch, 'gh pr comment 1 --body "A great solution — it works."')
    assert claude.main() == 0
    out = json.loads(capsys.readouterr().out)
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "allow"
    assert "Clean version." in spec["updatedInput"]["command"]
    assert "—" not in spec["updatedInput"]["command"]


def test_claude_allows_silently_when_already_clean(claude, monkeypatch, capsys):
    monkeypatch.setattr(claude, "_humanize", lambda t: t)  # scrubber is a no-op
    _feed(claude, monkeypatch, 'gh pr comment 1 --body "already clean"')
    assert claude.main() == 0
    assert capsys.readouterr().out == ""  # no rewrite emitted


def test_claude_skips_shell_expansion_body(claude, monkeypatch, capsys):
    monkeypatch.setattr(claude, "_humanize", lambda t: pytest.fail("should not run"))
    _feed(claude, monkeypatch, 'gh pr comment 1 --body "$(cat note.md)"')
    assert claude.main() == 0
    assert capsys.readouterr().out == ""


def test_claude_ignores_non_comment_commands(claude, monkeypatch, capsys):
    _feed(claude, monkeypatch, 'git commit -m "wip"')
    assert claude.main() == 0
    assert capsys.readouterr().out == ""


# --- cross-agent: block + suggest the humanized command -------------------


def test_multi_extract_command_dialects(multi):
    cmd = "gh pr comment 1 -b x"
    assert multi._extract_command({"tool_input": {"command": cmd}}) == cmd
    assert multi._extract_command({"command": cmd}) == cmd  # cursor top-level


def test_multi_blocks_and_suggests_humanized(multi, monkeypatch, capsys):
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean.")
    cmd = 'gh pr comment 1 --body "A great solution — it works."'
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 2
    err = capsys.readouterr().err
    assert "humanized" in err.lower()
    assert "Clean." in err


def test_multi_allows_when_clean(multi, monkeypatch):
    monkeypatch.setattr(multi, "_humanize", lambda t: t)
    cmd = 'gh pr comment 1 --body "clean"'
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 0


def test_multi_never_crashes_on_bad_stdin(multi, monkeypatch):
    monkeypatch.setattr(multi.sys, "stdin", io.StringIO("not json at all"))
    assert multi.main() == 0
