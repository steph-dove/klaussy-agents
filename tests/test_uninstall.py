"""Tests for `klaussy uninstall`.

Uninstall deletes files, so the tests that matter most are the ones asserting
what it does NOT touch. klaussy merges into `.gitignore` and each agent's
settings rather than owning them, and it appends its secret block to an existing
ignore file, so "delete everything klaussy might have written" would take the
user's work with it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from klaussy import uninstall
from klaussy.agents.backends import SECRET_IGNORE_MARKER
from klaussy.skills import VERSION_FILE


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repo carrying klaussy scaffolding plus user-owned content."""
    root = tmp_path / "demo"
    (root / ".claude" / "skills" / "demo-review").mkdir(parents=True)
    (root / ".claude" / "skills" / "demo-review" / "SKILL.md").write_text("---\nname: x\n---\n")
    (root / ".claude" / "skills" / VERSION_FILE).write_text("0.30.5\n")
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".claude" / "hooks" / "git_commit_guard.py").write_text("#!/usr/bin/env python3\n")

    # The user's own skill, sitting in the same directory klaussy scaffolds into.
    (root / ".claude" / "skills" / "my-own-skill").mkdir()
    (root / ".claude" / "skills" / "my-own-skill" / "SKILL.md").write_text("---\nname: mine\n---\n")

    (root / ".gitignore").write_text("node_modules/\n*.log\n\n# klaussy outputs\nplan.md\n")
    return root


def test_removes_scaffolded_skills_and_guards(repo):
    uninstall.apply(uninstall.plan(repo))
    assert not (repo / ".claude" / "skills" / "demo-review").exists()
    assert not (repo / ".claude" / "hooks").exists()


def test_leaves_a_user_authored_skill_alone(repo):
    uninstall.apply(uninstall.plan(repo))
    assert (repo / ".claude" / "skills" / "my-own-skill" / "SKILL.md").is_file()


def test_strips_only_klaussy_gitignore_entries(repo):
    uninstall.apply(uninstall.plan(repo))
    lines = (repo / ".gitignore").read_text().split()
    assert "node_modules/" in lines and "*.log" in lines
    assert "plan.md" not in lines


def test_dry_run_changes_nothing(repo):
    plan = uninstall.plan(repo)
    assert plan.removals
    assert (repo / ".claude" / "skills" / "demo-review").is_dir()


def test_conventions_are_kept_by_default(repo):
    (repo / "CLAUDE.md").write_text("# hand-edited\n")
    uninstall.apply(uninstall.plan(repo))
    assert (repo / "CLAUDE.md").is_file()


def test_conventions_go_with_include_conventions(repo):
    (repo / "CLAUDE.md").write_text("# hand-edited\n")
    uninstall.apply(uninstall.plan(repo, include_conventions=True))
    assert not (repo / "CLAUDE.md").exists()


# --- shared files are edited, never deleted ---------------------------------


def test_settings_keeps_user_hooks_and_other_keys(repo):
    settings = repo / ".claude" / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "env": {"MY_VAR": "keep-me"},
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"command": "klaussy-hook --packaged x"}]},
                        {"matcher": "Bash", "hooks": [{"command": "my-own-guard.sh"}]},
                    ]
                },
            }
        )
    )
    uninstall.apply(uninstall.plan(repo))

    data = json.loads(settings.read_text())
    assert data["env"] == {"MY_VAR": "keep-me"}
    assert "klaussy" not in json.dumps(data)
    assert "my-own-guard.sh" in json.dumps(data)


def test_a_settings_file_holding_only_klaussy_entries_is_removed(repo):
    settings = repo / ".gemini" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"hooks": {"BeforeTool": [{"command": "klaussy_read_guard.py"}]}})
    )
    uninstall.apply(uninstall.plan(repo))
    assert not settings.exists()


# --- ignore files: klaussy appends a block, it does not own the file --------


def test_ignore_file_keeps_user_entries_and_drops_the_block(repo):
    path = repo / ".cursorignore"
    path.write_text(f"# my own ignore\nsecret.txt\n\n{SECRET_IGNORE_MARKER}\n.env\n*.pem\n")
    uninstall.apply(uninstall.plan(repo))

    text = path.read_text()
    assert "secret.txt" in text
    assert SECRET_IGNORE_MARKER not in text


def test_ignore_file_is_deleted_when_it_held_only_the_block(repo):
    path = repo / ".geminiignore"
    path.write_text(f"{SECRET_IGNORE_MARKER}\n.env\n*.pem\n")
    uninstall.apply(uninstall.plan(repo))
    assert not path.exists()


def test_hand_written_ignore_file_is_untouched(repo):
    path = repo / ".clineignore"
    path.write_text("# entirely mine\nbuild/\n")
    plan = uninstall.plan(repo)
    uninstall.apply(plan)

    assert path.read_text() == "# entirely mine\nbuild/\n"
    assert any(".clineignore" in name for name, _ in plan.kept)


# --- generated configs are keyed on ownership -------------------------------


def test_generated_config_is_removed_when_every_key_is_klaussys(repo):
    path = repo / ".cursor" / "permissions.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"terminalAllowlist": ["git"], "mcpAllowlist": []}))
    uninstall.apply(uninstall.plan(repo))
    assert not path.exists()


def test_generated_config_survives_a_user_key(repo):
    path = repo / ".cursor" / "permissions.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"terminalAllowlist": ["git"], "myOwnKey": True}))
    uninstall.apply(uninstall.plan(repo))
    assert json.loads(path.read_text())["myOwnKey"] is True


def test_header_stamped_config_is_removed_only_with_the_stamp(repo):
    path = repo / ".codex" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text("# hand-written, not klaussy's\nmodel = 'x'\n")
    uninstall.apply(uninstall.plan(repo))
    assert path.is_file()

    path.write_text("# Generated by klaussy. Codex project config.\nmodel = 'x'\n")
    uninstall.apply(uninstall.plan(repo))
    assert not path.exists()


def test_plan_is_empty_on_a_repo_klaussy_never_touched(tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "app.py").write_text("x = 1\n")
    assert uninstall.plan(clean).is_empty
