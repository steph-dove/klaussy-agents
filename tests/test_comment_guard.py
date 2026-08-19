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


# --- file-backed bodies (--body-file / -F) --------------------------------


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_detects_pr_and_issue_bodies(mod_name, claude, multi):
    """A PR/issue body is prose we post too, not just a comment."""
    mod = {"claude": claude, "multi": multi}[mod_name]
    assert mod._is_comment_post("gh pr create --title t --body-file /tmp/b.md")
    assert mod._is_comment_post("gh pr edit 38 --body-file /tmp/b.md")
    assert mod._is_comment_post("gh issue create --title t -F /tmp/b.md")
    assert not mod._is_comment_post("gh pr checkout 38")


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_find_body_file_forms(mod_name, claude, multi):
    mod = {"claude": claude, "multi": multi}[mod_name]
    assert mod._find_body_file(shlex.split("gh pr comment 1 -F /tmp/b.md")) == "/tmp/b.md"
    assert mod._find_body_file(shlex.split("gh pr create --body-file /tmp/b.md")) == "/tmp/b.md"
    assert mod._find_body_file(shlex.split("gh pr create --body-file=/tmp/b.md")) == "/tmp/b.md"
    assert mod._find_body_file(shlex.split('gh pr comment 1 --body "x"')) is None


@pytest.fixture()
def body_file(tmp_path):
    path = tmp_path / "body.md"
    path.write_text("A great solution — it works.", encoding="utf-8")
    return path


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_body_file_is_scrubbed_in_place(mod_name, claude, multi, monkeypatch, body_file):
    mod = {"claude": claude, "multi": multi}[mod_name]
    monkeypatch.setattr(mod, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(mod, "_is_untracked", lambda p: True)
    note, scrubbed = mod._humanize_file(str(body_file))
    assert scrubbed and "humanized" in note
    assert body_file.read_text(encoding="utf-8") == "Clean version."


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_tracked_body_file_is_left_alone(mod_name, claude, multi, monkeypatch, body_file):
    """Pointing --body-file at a committed doc must not mutate the repo."""
    mod = {"claude": claude, "multi": multi}[mod_name]
    monkeypatch.setattr(mod, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(mod, "_is_untracked", lambda p: False)
    note, scrubbed = mod._humanize_file(str(body_file))
    assert not scrubbed and "is tracked" in note  # reported, not silently allowed
    assert "—" in body_file.read_text(encoding="utf-8")  # left exactly as committed


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_unreadable_body_file_is_allowed(mod_name, claude, multi, monkeypatch, tmp_path):
    mod = {"claude": claude, "multi": multi}[mod_name]
    monkeypatch.setattr(mod, "_humanize", lambda t: pytest.fail("should not run"))
    assert mod._humanize_file(str(tmp_path / "missing.md")) is None
    assert mod._humanize_file("-") is None
    assert mod._humanize_file("$TMPDIR/body.md") is None


def test_claude_scrubs_pr_body_file_and_notes_it(claude, monkeypatch, capsys, body_file):
    monkeypatch.setattr(claude, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(claude, "_is_untracked", lambda p: True)
    _feed(claude, monkeypatch, f"gh pr create --title t --body-file {body_file}")
    assert claude.main() == 0
    assert "humanized" in json.loads(capsys.readouterr().out)["systemMessage"]
    assert body_file.read_text(encoding="utf-8") == "Clean version."


def test_claude_body_file_stays_quiet_when_clean(claude, monkeypatch, capsys, body_file):
    monkeypatch.setattr(claude, "_humanize", lambda t: t)
    monkeypatch.setattr(claude, "_is_untracked", lambda p: True)
    _feed(claude, monkeypatch, f"gh pr comment 1 --body-file {body_file}")
    assert claude.main() == 0
    assert capsys.readouterr().out == ""


def test_multi_scrubs_body_file_without_blocking(multi, monkeypatch, body_file):
    """The file is already fixed, so there's nothing to make the agent re-issue."""
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(multi, "_is_untracked", lambda p: True)
    cmd = f"gh pr create --title t --body-file {body_file}"
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 0
    assert body_file.read_text(encoding="utf-8") == "Clean version."


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_untracked_check_fails_closed(mod_name, claude, multi, monkeypatch):
    """Only git saying it tracks the file (exit 0) stops a rewrite."""
    mod = {"claude": claude, "multi": multi}[mod_name]

    class _Result:
        def __init__(self, code, stderr=""):
            self.returncode = code
            self.stderr = stderr

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _Result(1))
    assert mod._is_untracked("/tmp/body.md") is True  # in a repo, not tracked
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: _Result(128, "fatal: not a git repository")
    )
    assert mod._is_untracked("/tmp/body.md") is True  # no repo owns it
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: _Result(128, "fatal: detected dubious ownership")
    )
    assert mod._is_untracked("README.md") is None  # git failed, it didn't answer
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _Result(0))
    assert mod._is_untracked("README.md") is False  # tracked

    def _boom(*a, **k):
        raise OSError("no git")

    monkeypatch.setattr(mod.subprocess, "run", _boom)
    assert mod._is_untracked("README.md") is None  # git missing — can't tell


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_failed_write_leaves_original_intact(mod_name, claude, multi, monkeypatch, body_file):
    """A part-way write must never hand `gh` a truncated body."""
    mod = {"claude": claude, "multi": multi}[mod_name]
    monkeypatch.setattr(mod, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(mod, "_is_untracked", lambda p: True)

    def _boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(mod.Path, "write_text", _boom)
    note, scrubbed = mod._humanize_file(str(body_file))
    assert not scrubbed and "couldn't rewrite" in note  # reported, not silently allowed
    assert body_file.read_text(encoding="utf-8") == "A great solution — it works."
    assert not list(body_file.parent.glob("*.klaussy-tmp"))  # temp file cleaned up


# --- chained commands: only the `gh` segment is ours -----------------------


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_split_commands_separates_chained_commands(mod_name, claude, multi):
    mod = {"claude": claude, "multi": multi}[mod_name]
    # Unpadded separators glue into shlex tokens, so the split has to happen on
    # the raw string: 'x;' would otherwise keep git's -F inside the gh command.
    parts = mod._split_commands('gh pr comment 1 --body "x"; git commit -F /tmp/msg.txt')
    assert len(parts) == 2
    assert "/tmp/msg.txt" not in parts[0]
    assert mod._is_comment_post(parts[0])
    assert not mod._is_comment_post(parts[1])
    assert len(mod._split_commands("gh pr comment 1 -b x&&git commit -F m")) == 2
    # A newline separates commands too — agents send multi-line Bash regularly.
    newline_chained = mod._split_commands('gh pr comment 1 --body "x"\ngit commit -F /tmp/m')
    assert len(newline_chained) == 2
    assert mod._find_body_file(shlex.split(newline_chained[0])) is None
    # A separator inside quotes is body text, not an operator — markdown tables
    # are full of pipes and must not split the command.
    tabled = mod._split_commands('gh pr comment 1 --body "| a | b |\n| - | - |"')
    assert len(tabled) == 1


def test_claude_ignores_a_chained_commands_body_flag(claude, monkeypatch, capsys):
    """`git commit -F msg` must not be mistaken for the comment body file."""
    monkeypatch.setattr(claude, "_humanize", lambda t: "Clean.")
    monkeypatch.setattr(
        claude, "_humanize_file", lambda p: pytest.fail(f"scrubbed the wrong file: {p}")
    )
    _feed(
        claude,
        monkeypatch,
        'git commit -F /tmp/msg.txt && gh pr comment 1 --body "A solution — it works."',
    )
    assert claude.main() == 0
    out = json.loads(capsys.readouterr().out)
    # No rewrite: reassembling a chained line isn't safe. But it's reported, so
    # the body with tells doesn't post in silence.
    assert "hookSpecificOutput" not in out
    assert "chained" in out["systemMessage"]


def test_multi_ignores_a_chained_commands_body_flag(multi, monkeypatch, capsys):
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean.")
    monkeypatch.setattr(
        multi, "_humanize_file", lambda p: pytest.fail(f"scrubbed the wrong file: {p}")
    )
    cmd = 'git commit -F /tmp/msg.txt && gh pr comment 1 --body "A solution — it works."'
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 2  # blocked, with the reason
    err = capsys.readouterr().err
    assert "its own command" in err
    assert "/tmp/msg.txt" not in err  # git's file was never in scope


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_split_commands_handles_escaped_quotes(mod_name, claude, multi):
    r"""An escaped \" inside a body must not be read as the closing quote."""
    mod = {"claude": claude, "multi": multi}[mod_name]
    cmd = 'gh pr comment 1 --body "he said \\"hi\\"" && git commit -F /tmp/msg.txt'
    parts = mod._split_commands(cmd)
    assert len(parts) == 2
    assert "/tmp/msg.txt" not in parts[0]
    assert mod._find_body_file(shlex.split(parts[0])) is None  # git's -F stays git's
    # A backslash inside single quotes is literal, so it must not eat the quote.
    assert len(mod._split_commands("gh pr comment 1 --body 'a\\\\' ; git commit -F m")) == 2


def test_multi_reports_collected_notes_when_it_blocks(multi, monkeypatch, capsys, body_file):
    """A note from an earlier --body-file must survive a later block."""
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean.")
    monkeypatch.setattr(multi, "_is_untracked", lambda p: False)  # tracked → note only
    cmd = f'gh pr comment 1 --body-file {body_file} && gh pr comment 2 --body "tells —"'
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 2
    err = capsys.readouterr().err
    assert "is tracked" in err  # the earlier note wasn't swallowed by the block
    assert "its own command" in err


@pytest.mark.parametrize("mod_name", ["claude", "multi"])
def test_missing_git_is_reported_as_such(mod_name, claude, multi, monkeypatch, body_file):
    """ "Couldn't check" must not be dressed up as "the file is tracked"."""
    mod = {"claude": claude, "multi": multi}[mod_name]
    monkeypatch.setattr(mod, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(mod, "_is_untracked", lambda p: None)
    note, scrubbed = mod._humanize_file(str(body_file))
    assert not scrubbed
    assert "couldn't check git" in note
    assert "is tracked" not in note


def test_multi_blocks_when_a_body_file_posts_unscrubbed(multi, monkeypatch, capsys, body_file):
    """A note on an allowed call may never surface, so an unscrubbed body blocks."""
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(multi, "_is_untracked", lambda p: False)  # tracked, left alone
    cmd = f"gh pr comment 1 --body-file {body_file}"
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 2
    assert "is tracked" in capsys.readouterr().err


def test_multi_allows_quietly_when_the_body_file_was_scrubbed(multi, monkeypatch, body_file):
    monkeypatch.setattr(multi, "_humanize", lambda t: "Clean version.")
    monkeypatch.setattr(multi, "_is_untracked", lambda p: True)
    cmd = f"gh pr comment 1 --body-file {body_file}"
    monkeypatch.setattr(
        multi.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
    )
    assert multi.main() == 0  # nothing to block: the file now holds clean text
    assert body_file.read_text(encoding="utf-8") == "Clean version."
