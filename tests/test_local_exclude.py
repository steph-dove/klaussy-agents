"""Tests for `klaussy init --local`.

The promise is narrow: what klaussy created disappears from `git status` for
this clone, and nothing committed changes. So most tests assert on what git
reports afterwards, and on what was left alone.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from klaussy import local_exclude, uninstall
from klaussy.cli import app

runner = CliRunner()


def git(repo: Path, *args: str) -> str:
    cmd = ["git", "-C", str(repo), *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def status(repo: Path) -> list[str]:
    out = git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    return sorted(record[3:] for record in out.split("\0") if record)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t.co")
    git(root, "config", "user.name", "t")
    (root / "app.py").write_text("x = 1\n")
    git(root, "add", "app.py")
    git(root, "commit", "-qm", "base")
    return root


def run_local(repo: Path, scaffold) -> local_exclude.LocalResult:
    top = local_exclude.toplevel(repo)
    before = local_exclude.snapshot(top)
    scaffold()
    return local_exclude.apply(top, before)


def exclude_text(repo: Path) -> str:
    return local_exclude.exclude_file(repo).read_text()


def test_created_files_vanish_from_git_status(repo):
    def scaffold():
        (repo / ".claude" / "skills" / "demo-review").mkdir(parents=True)
        (repo / ".claude" / "skills" / "demo-review" / "SKILL.md").write_text("x\n")
        (repo / "CLAUDE.md").write_text("# conventions\n")

    result = run_local(repo, scaffold)

    assert result.excluded == [".claude/skills/demo-review/SKILL.md", "CLAUDE.md"]
    assert status(repo) == []


def test_output_files_are_ignored_without_touching_gitignore(repo):
    run_local(repo, lambda: None)
    (repo / "plan.md").write_text("plan\n")
    assert status(repo) == []
    assert not (repo / ".gitignore").exists()


def test_a_users_own_untracked_file_stays_visible(repo):
    (repo / "notes.txt").write_text("mine\n")
    run_local(repo, lambda: (repo / "CLAUDE.md").write_text("x\n"))
    assert status(repo) == ["notes.txt"]
    assert "notes.txt" not in exclude_text(repo)


def test_a_committed_file_klaussy_edits_is_put_back(repo):
    (repo / "AGENTS.md").write_text("team conventions\n")
    git(repo, "add", "AGENTS.md")
    git(repo, "commit", "-qm", "agents")

    result = run_local(repo, lambda: (repo / "AGENTS.md").write_text("klaussy's version\n"))

    assert result.restored == [("AGENTS.md", None)]
    assert (repo / "AGENTS.md").read_text() == "team conventions\n"
    assert status(repo) == []


def test_a_committed_file_keeps_the_users_own_uncommitted_edits(repo):
    (repo / "AGENTS.md").write_text("team\n")
    git(repo, "add", "AGENTS.md")
    git(repo, "commit", "-qm", "agents")
    (repo / "AGENTS.md").write_text("team plus my edit\n")

    run_local(repo, lambda: (repo / "AGENTS.md").write_text("klaussy's version\n"))

    assert (repo / "AGENTS.md").read_text() == "team plus my edit\n"


def test_committed_claude_settings_move_to_settings_local(repo):
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    team = {"permissions": {"allow": ["Bash(npm test)"]}, "model": "sonnet"}
    settings.write_text(json.dumps(team, indent=2) + "\n")
    git(repo, "add", ".claude/settings.json")
    git(repo, "commit", "-qm", "settings")
    committed = settings.read_text()
    hook = {"matcher": "Bash", "hooks": [{"command": "klaussy-hook x"}]}

    def scaffold():
        data = json.loads(settings.read_text())
        data["permissions"]["allow"].append("Bash(pytest *)")
        data["hooks"] = {"PreToolUse": [hook]}
        settings.write_text(json.dumps(data, indent=2))

    result = run_local(repo, scaffold)

    assert result.moved_to_local == [".claude/settings.json"]
    assert settings.read_text() == committed
    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert local == {
        "permissions": {"allow": ["Bash(pytest *)"]},
        "hooks": {"PreToolUse": [hook]},
    }
    assert status(repo) == []


def test_settings_local_keeps_what_the_user_already_had(repo):
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {"allow": []}}\n')
    git(repo, "add", ".claude/settings.json")
    git(repo, "commit", "-qm", "settings")
    local_file = repo / ".claude" / "settings.local.json"
    local_file.write_text('{"permissions": {"allow": ["Bash(ls)"]}}\n')

    run_local(repo, lambda: settings.write_text('{"permissions": {"allow": ["Bash(pytest *)"]}}'))

    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert local == {"permissions": {"allow": ["Bash(ls)", "Bash(pytest *)"]}}


def test_a_broken_settings_local_is_named_and_nothing_changes(repo):
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {"allow": []}}\n')
    git(repo, "add", ".claude/settings.json")
    git(repo, "commit", "-qm", "settings")
    committed = settings.read_text()
    local_file = repo / ".claude" / "settings.local.json"
    local_file.write_text("{ not json")

    result = run_local(repo, lambda: settings.write_text('{"permissions": {"allow": ["x"]}}'))

    assert result.moved_to_local == []
    [(rel, why)] = result.restored
    assert rel == ".claude/settings.json"
    assert "settings.local.json isn't valid JSON" in why
    assert settings.read_text() == committed
    assert local_file.read_text() == "{ not json"


def test_a_restore_git_refuses_is_reported_as_failed(repo, monkeypatch):
    (repo / "AGENTS.md").write_text("team\n")
    git(repo, "add", "AGENTS.md")
    git(repo, "commit", "-qm", "agents")
    real_git = local_exclude._git

    def refuse_checkout(top, *args):
        if args[:1] == ("checkout",):
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: index.lock exists")
        return real_git(top, *args)

    top = local_exclude.toplevel(repo)
    before = local_exclude.snapshot(top)
    (repo / "AGENTS.md").write_text("klaussy's version\n")
    monkeypatch.setattr(local_exclude, "_git", refuse_checkout)
    result = local_exclude.apply(top, before)

    assert result.restored == []
    assert result.failed == [("AGENTS.md", "fatal: index.lock exists")]


def test_a_rerun_keeps_earlier_files_and_drops_deleted_ones(repo):
    run_local(repo, lambda: [(repo / n).write_text("x\n") for n in ("CLAUDE.md", "GEMINI.md")])
    (repo / "GEMINI.md").unlink()

    result = run_local(repo, lambda: (repo / "AGENTS.md").write_text("x\n"))

    assert result.excluded == ["AGENTS.md", "CLAUDE.md"]
    assert "/GEMINI.md" not in exclude_text(repo)


def test_the_block_leaves_existing_exclude_lines_alone(repo):
    exclude = local_exclude.exclude_file(repo)
    exclude.write_text("# my own\n*.scratch\n")

    run_local(repo, lambda: (repo / "CLAUDE.md").write_text("x\n"))
    assert exclude.read_text().startswith("# my own\n*.scratch\n")

    assert local_exclude.remove_block(repo)
    assert exclude.read_text() == "# my own\n*.scratch\n"


def test_odd_characters_in_a_path_are_matched_literally(repo):
    name = "notes [draft]*.md"
    run_local(repo, lambda: (repo / name).write_text("x\n"))
    (repo / "notes d*.md").write_text("mine\n")
    assert status(repo) == ["notes d*.md"]


def test_worktrees_share_the_clones_exclude_file(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    run_local(wt, lambda: (wt / "CLAUDE.md").write_text("x\n"))
    assert local_exclude.exclude_file(wt) == local_exclude.exclude_file(repo)
    assert status(wt) == []


def test_uninstall_removes_the_block(repo):
    run_local(repo, lambda: (repo / "CLAUDE.md").write_text("x\n"))
    computed = uninstall.plan(repo)
    assert any(e.path == uninstall.LOCAL_EXCLUDE_EDIT for e in computed.edits)
    uninstall.apply(computed)
    assert not local_exclude.has_block(repo)
    assert status(repo) == ["CLAUDE.md"]


def test_init_local_end_to_end(repo, monkeypatch):
    monkeypatch.setattr(
        "klaussy.cli.run_init",
        lambda repo, **_: (repo / "CLAUDE.md").write_text("# demo\n\n## Commands\n\n- `pytest`\n"),
    )
    result = runner.invoke(
        app, ["init", "--repo", str(repo), "--agents", "claude", "-b", "main", "--local"]
    )
    assert result.exit_code == 0, result.output
    assert "added to .git/info/exclude" in result.output
    assert status(repo) == []
    assert (repo / "CLAUDE.md").is_file()
    assert any((repo / ".claude" / "skills").iterdir())
    assert not (repo / ".gitignore").exists()


def test_a_later_plain_init_stays_local(repo, monkeypatch):
    # `klaussy init --force` is how people update; it mustn't unhide 400 files.
    monkeypatch.setattr(
        "klaussy.cli.run_init", lambda repo, **_: (repo / "CLAUDE.md").write_text("# demo\n")
    )
    args = ["init", "--repo", str(repo), "--agents", "claude", "-b", "main"]
    runner.invoke(app, [*args, "--local"])
    result = runner.invoke(app, [*args, "--force"])
    assert result.exit_code == 0, result.output
    assert "This clone uses --local" in result.output
    assert status(repo) == []
    assert not (repo / ".gitignore").exists()


def test_no_local_shows_the_files_again(repo, monkeypatch):
    monkeypatch.setattr(
        "klaussy.cli.run_init", lambda repo, **_: (repo / "CLAUDE.md").write_text("# demo\n")
    )
    args = ["init", "--repo", str(repo), "--agents", "claude", "-b", "main"]
    runner.invoke(app, [*args, "--local"])
    result = runner.invoke(app, [*args, "--no-local"])
    assert result.exit_code == 0, result.output
    assert not local_exclude.has_block(repo)
    assert "CLAUDE.md" in status(repo)


def test_local_outside_a_repo_fails_cleanly(tmp_path):
    result = runner.invoke(app, ["init", "--repo", str(tmp_path), "-b", "main", "--local"])
    assert result.exit_code == 1
    assert "needs a git repository" in result.output
