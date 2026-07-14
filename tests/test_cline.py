"""Tests for the Cline backend.

Validates `.clinerules/` generation, `.clineignore` emission, and event-named
hooks execution.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.agents.backends import ClineBackend
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


class TestClineRegistration:
    def test_registered_in_backends(self):
        assert "cline" in BACKENDS
        assert "cline" in ALL_AGENTS

    def test_resolve_selects_cline(self):
        assert resolve_agents("cline") == ["cline"]


class TestClineConventions:
    def test_project_wide_to_always_on_rule(self, repo_with_rules):
        ClineBackend().emit_conventions(repo_with_rules, force=True)
        conventions = (repo_with_rules / ".clinerules" / "conventions.md").read_text()
        assert "snake_case" in conventions
        assert "paths:" not in conventions

    def test_path_scoped_rule_uses_paths_frontmatter(self, repo_with_rules):
        ClineBackend().emit_conventions(repo_with_rules, force=True)
        rule = (repo_with_rules / ".clinerules" / "api.md").read_text()
        assert rule.startswith("---\npaths:\n")
        assert '- "src/api/**/*.py"' in rule
        assert "Pydantic validation" in rule

    def test_no_claude_md_warns_and_skips(self, repo):
        ClineBackend().emit_conventions(repo, force=True)
        assert not (repo / ".clinerules" / "conventions.md").exists()


class TestClineSkills:
    def test_skills_land_in_cross_tool_agents_dir(self, repo_with_rules):
        ns = sanitize_skill_namespace(repo_with_rules.name)
        ClineBackend().run_skills(
            repo_with_rules, force=True, base_branch="main", review_template=None
        )
        assert (repo_with_rules / ".agents" / "skills" / f"{ns}-plan" / "SKILL.md").exists()
        # Skills are kept out of .clinerules to avoid prompt pollution.
        assert not (repo_with_rules / ".clinerules" / "skills").exists()


class TestClineSettings:
    def test_clineignore_excludes_secrets(self, repo):
        ClineBackend().emit_settings(repo, force=True)
        ignore = (repo / ".clineignore").read_text()
        assert ".env" in ignore
        # Cline auto-approval is GUI-only, so no settings file is written.
        assert not (repo / ".cline" / "settings.json").exists()


class TestClineHooks:
    def test_event_named_executables_and_shared_guards(self, repo):
        ClineBackend().emit_hooks(repo, force=True)
        hooks = repo / ".clinerules" / "hooks"
        for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
            path = hooks / event
            assert path.is_file(), f"missing {event}"
            assert os.access(path, os.X_OK), f"{event} not executable"
            assert path.stat().st_mode & stat.S_IXUSR
        # PreToolUse and PostToolUse use the same bridge shim.
        assert (hooks / "PreToolUse").read_text() == (hooks / "PostToolUse").read_text()
        assert "cancel" in (hooks / "PreToolUse").read_text()
        # Commit guard is written because lint/format is detected.
        assert (hooks / "klaussy_commit_guard.py").exists()
        assert (hooks / "klaussy_comment_guard.py").exists()
        assert (hooks / "klaussy_read_guard.py").exists()

    def test_plan_guidance_bakes_cline_dialect(self, repo):
        ClineBackend().emit_hooks(repo, force=True)
        guidance = (repo / ".clinerules" / "hooks" / "UserPromptSubmit").read_text()
        # DIALECT is baked via repr(), so it lands single-quoted.
        assert "DIALECT: str = 'cline'" in guidance

    def test_commit_guard_skipped_without_lint_or_format(self, tmp_path):
        # No pyproject.toml/package.json → no lint/format command detected.
        ClineBackend().emit_hooks(tmp_path, force=True)
        hooks = tmp_path / ".clinerules" / "hooks"
        assert not (hooks / "klaussy_commit_guard.py").exists()
        assert (hooks / "klaussy_comment_guard.py").exists()
        assert (hooks / "PreToolUse").is_file()
