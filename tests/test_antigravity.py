"""Tests for the Google Antigravity backend.

Antigravity reads the cross-tool `AGENTS.md` standard for project-wide
conventions; its Claude-compatible CLI loads a committed plugin under
`.gemini/antigravity-cli/plugins/klaussy/` carrying skills, glob-activated
rules, and the commit/read-injection guards (hooks.json). These tests pin those
output paths/formats and the best-effort workspace allowlist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.agents.backends import ANTIGRAVITY_PLUGIN, AntigravityBackend
from klaussy.skills import sanitize_skill_namespace

SAMPLE_CLAUDE_MD = """\
# CLAUDE.md - test-project

## Tech Stack

- python
- pytest

## Conventions

- **snake_case** for all function and variable names
"""

SAMPLE_RULE_FILE = """\
---
paths:
  - "src/api/**/*.py"
---

# Rules for `src/api/**/*.py`

## Conventions

- **Pydantic validation**: Uses Pydantic for input validation.
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    return tmp_path


@pytest.fixture()
def repo_with_rules(repo: Path) -> Path:
    (repo / "CLAUDE.md").write_text(SAMPLE_CLAUDE_MD)
    rules_dir = repo / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "api.md").write_text(SAMPLE_RULE_FILE)
    return repo


class TestAntigravityRegistration:
    def test_registered_in_backends(self):
        assert "antigravity" in BACKENDS
        assert "antigravity" in ALL_AGENTS

    def test_resolve_selects_antigravity(self):
        assert resolve_agents("antigravity") == ["antigravity"]


class TestAntigravityConventions:
    def test_project_wide_to_agents_md_without_inlined_rules(self, repo_with_rules):
        AntigravityBackend().emit_conventions(repo_with_rules, force=True)
        agents_md = (repo_with_rules / "AGENTS.md").read_text()
        assert "snake_case" in agents_md
        # Path-scoped rules live in the plugin's rules/, not inlined in AGENTS.md.
        assert "Path-scoped rules" not in agents_md

    def test_path_scoped_rule_uses_glob_trigger(self, repo_with_rules):
        AntigravityBackend().emit_conventions(repo_with_rules, force=True)
        rule = (repo_with_rules / ANTIGRAVITY_PLUGIN / "rules" / "api.md").read_text()
        assert "trigger: glob" in rule
        assert "globs: src/api/**/*.py" in rule
        assert "Pydantic validation" in rule

    def test_no_claude_md_warns_and_skips(self, repo):
        AntigravityBackend().emit_conventions(repo, force=True)
        assert not (repo / "AGENTS.md").exists()


class TestAntigravitySkills:
    def test_skills_land_in_plugin(self, repo_with_rules):
        ns = sanitize_skill_namespace(repo_with_rules.name)
        AntigravityBackend().run_skills(
            repo_with_rules, force=True, base_branch="main", review_template=None
        )
        assert (
            repo_with_rules / ANTIGRAVITY_PLUGIN / "skills" / f"{ns}-plan" / "SKILL.md"
        ).exists()


class TestAntigravitySettings:
    def test_best_effort_terminal_allowlist(self, repo):
        AntigravityBackend().emit_settings(repo, force=True)
        settings = json.loads((repo / ".agents" / "settings.json").read_text())
        allow = settings["terminal"]["allowList"]
        assert "git" in allow
        assert "pytest" in allow
        assert settings["terminal"]["denyList"] == []


class TestAntigravityHooks:
    def test_plugin_marker_and_hooks_wired(self, repo):
        AntigravityBackend().emit_hooks(repo, force=True)
        plugin = repo / ANTIGRAVITY_PLUGIN
        # Required plugin marker.
        marker = json.loads((plugin / "plugin.json").read_text())
        assert marker["name"] == "klaussy"
        # Claude-style EVENTS but Antigravity-native TOOL matchers, grouped under
        # the plugin name (not a "hooks" key): read guard on PreToolUse view_file
        # + PostToolUse read_url_content; commit guard on PreToolUse run_command.
        hooks = json.loads((plugin / "hooks.json").read_text())["klaussy"]
        pre_matchers = {entry["matcher"] for entry in hooks["PreToolUse"]}
        post_matchers = {entry["matcher"] for entry in hooks["PostToolUse"]}
        assert "view_file" in pre_matchers
        assert "run_command" in pre_matchers  # pyproject.toml → lint/format detected
        assert "read_url_content" in post_matchers
        # Guard scripts installed inside the plugin.
        assert (plugin / "hooks" / "klaussy_read_guard.py").exists()
        assert (plugin / "hooks" / "klaussy_commit_guard.py").exists()
