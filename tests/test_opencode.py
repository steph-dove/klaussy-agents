"""Tests for the OpenCode backend.

Validates `AGENTS.md` and `.opencode/rules/` generation, `.opencode/opencode.json` settings,
and skill placement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.agents.backends import CursorBackend, OpenCodeBackend
from klaussy.agents.render import adapt_body
from klaussy.hooks import read_pre_plan_guidance
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


class TestOpenCodeRegistration:
    def test_registered_in_backends(self):
        assert "opencode" in BACKENDS
        assert "opencode" in ALL_AGENTS

    def test_resolve_selects_opencode(self):
        assert resolve_agents("opencode") == ["opencode"]


class TestOpenCodeConventions:
    def test_project_wide_to_agents_md(self, repo_with_rules):
        OpenCodeBackend().emit_conventions(repo_with_rules, force=True)
        agents_md = (repo_with_rules / "AGENTS.md").read_text()
        assert "snake_case" in agents_md
        assert "Pydantic validation" not in agents_md

    def test_path_scoped_rule_written_with_scope_heading(self, repo_with_rules):
        OpenCodeBackend().emit_conventions(repo_with_rules, force=True)
        rule = (repo_with_rules / ".opencode" / "rules" / "api.md").read_text()
        # opencode ignores unknown frontmatter, so the glob is a human-readable
        # heading rather than a (non-functional) `globs:` frontmatter key.
        assert rule.startswith("# Rules for `src/api/**/*.py`")
        assert "Pydantic validation" in rule

    def test_no_claude_md_warns_and_skips(self, repo):
        OpenCodeBackend().emit_conventions(repo, force=True)
        assert not (repo / "AGENTS.md").exists()


class TestOpenCodePrePlanGuidance:
    """opencode can't inject plan guidance via a hook (no context-injection
    event), so — like Antigravity's .antigravityrules — it rides an always-loaded
    instructions rule written by emit_conventions."""

    GUIDANCE_PATH = Path(".opencode") / "rules" / "klaussy-pre-plan-guidance.md"

    def test_guidance_rule_written_with_canonical_text(self, repo_with_rules):
        OpenCodeBackend().emit_conventions(repo_with_rules, force=True)
        guidance = (repo_with_rules / self.GUIDANCE_PATH).read_text()
        assert guidance == read_pre_plan_guidance()

    def test_guidance_rule_written_even_without_path_scoped_rules(self, repo):
        # No .claude/rules/, but CLAUDE.md exists: the guidance must still land so
        # opencode reaches Claude-level guardrail parity regardless of rule count.
        (repo / "CLAUDE.md").write_text(SAMPLE_CLAUDE_MD)
        OpenCodeBackend().emit_conventions(repo, force=True)
        assert (repo / self.GUIDANCE_PATH).exists()

    def test_guidance_rule_is_covered_by_instructions_glob(self, repo_with_rules):
        # The guidance only loads because emit_settings wires .opencode/rules/*.md
        # into `instructions`; pin that the reserved file matches that glob.
        OpenCodeBackend().emit_conventions(repo_with_rules, force=True)
        OpenCodeBackend().emit_settings(repo_with_rules, force=True)
        config = json.loads((repo_with_rules / "opencode.json").read_text())
        assert ".opencode/rules/*.md" in config["instructions"]
        assert self.GUIDANCE_PATH.match(".opencode/rules/*.md")

    def test_no_claude_md_skips_guidance(self, repo):
        # No CLAUDE.md → conventions bail before any file is written, guidance too.
        OpenCodeBackend().emit_conventions(repo, force=True)
        assert not (repo / self.GUIDANCE_PATH).exists()


class TestOpenCodeSkills:
    def test_skills_land_in_opencode_skills_dir(self, repo_with_rules):
        ns = sanitize_skill_namespace(repo_with_rules.name)
        OpenCodeBackend().run_skills(
            repo_with_rules, force=True, base_branch="main", review_template=None
        )
        assert (repo_with_rules / ".opencode" / "skills" / f"{ns}-plan" / "SKILL.md").exists()


class TestOpenCodeSettings:
    def test_settings_generates_valid_permissions_json(self, repo):
        OpenCodeBackend().emit_settings(repo, force=True)
        # opencode discovers config at the repo root, not inside .opencode/.
        config_path = repo / "opencode.json"
        assert config_path.exists()
        assert not (repo / ".opencode" / "opencode.json").exists()

        config = json.loads(config_path.read_text())
        assert "permission" in config
        assert "read" in config["permission"]
        assert "bash" in config["permission"]

        # Verify read rules (sensitive files denied)
        assert config["permission"]["read"][".env"] == "deny"
        assert config["permission"]["read"]["*.pem"] == "deny"
        assert config["permission"]["read"]["*"] == "allow"

        # Verify bash rules (python, pytest allow-listed since pyproject.toml is in repo)
        assert config["permission"]["bash"]["pytest"] == "allow"
        assert config["permission"]["bash"]["pytest *"] == "allow"
        assert config["permission"]["bash"]["*"] == "ask"

    def test_wildcard_default_is_first_so_specific_rules_win(self, repo):
        # opencode is last-match-wins: the broad "*" must precede the specific
        # allow/deny rules, or it would re-allow secret reads / re-gate the
        # allow-list. Pin the ordering, not just membership.
        OpenCodeBackend().emit_settings(repo, force=True)
        config = json.loads((repo / "opencode.json").read_text())
        read_keys = list(config["permission"]["read"])
        bash_keys = list(config["permission"]["bash"])
        assert read_keys[0] == "*"
        assert bash_keys[0] == "*"
        assert read_keys.index("*") < read_keys.index(".env")

    def test_path_scoped_rules_are_wired_into_instructions(self, repo):
        # Rule files under .opencode/rules/ load only if referenced here.
        OpenCodeBackend().emit_settings(repo, force=True)
        config = json.loads((repo / "opencode.json").read_text())
        assert ".opencode/rules/*.md" in config["instructions"]


class TestOpenCodeSubagentAndPlanAdaptation:
    """opencode has real parallel subagents (`@`-mention) and a Plan agent, so
    its skill banner names them affirmatively instead of the generic "use your
    equivalent, else go sequential" hedge the other non-Claude backends get."""

    SUBAGENT_BODY = "Use the Agent tool to launch all selected sub-agents in parallel."
    PLAN_BODY = "Enter plan mode and present findings before editing."
    # Signature phrase unique to the generic (mechanism-less) banner.
    GENERIC_MARKER = "Most coding agents now have their own"

    def test_subagent_banner_names_opencode_mechanism(self):
        out = adapt_body(self.SUBAGENT_BODY, OpenCodeBackend.profile)
        assert "@general" in out
        assert "parallel child sessions" in out
        # The generic "or go sequential" hedge (and its other-agent examples) is
        # replaced, not appended.
        assert self.GENERIC_MARKER not in out
        assert "Cursor's `Task`" not in out

    def test_plan_banner_names_plan_agent(self):
        out = adapt_body(self.PLAN_BODY, OpenCodeBackend.profile)
        assert "Plan agent" in out
        # Not the generic "use your agent's own plan/approval mode" fallback.
        assert "own plan/approval mode" not in out

    def test_generic_backend_still_gets_generic_banner(self):
        # Regression guard: a backend with no mechanism strings keeps the generic
        # note, so this enrichment stays opencode-scoped.
        out = adapt_body(self.SUBAGENT_BODY, CursorBackend.profile)
        assert self.GENERIC_MARKER in out
        assert "@general" not in out

    def test_no_banner_when_body_references_neither(self):
        # A simple skill (no fan-out / plan refs) gets no banner at all.
        out = adapt_body("Run the formatter and commit.", OpenCodeBackend.profile)
        assert "Adapted for" not in out


class TestOpenCodeHooks:
    def test_hooks_install_bridge_plugin_and_guards(self, repo):
        OpenCodeBackend().emit_hooks(repo, force=True)
        plugin = repo / ".opencode" / "plugins" / "klaussy.js"
        assert plugin.exists()
        plugin_src = plugin.read_text()
        assert "tool.execute.before" in plugin_src
        assert "export const klaussy" in plugin_src
        # The guards the plugin shells out to are installed alongside it.
        hooks_dir = repo / ".opencode" / "hooks"
        for guard in (
            "klaussy_read_guard.py",
            "klaussy_comment_guard.py",
            "klaussy_dependency_guard.py",
        ):
            assert (hooks_dir / guard).exists()
