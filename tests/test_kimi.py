"""Tests for the Kimi Code CLI backend.

Covers `.kimi-code/AGENTS.md` conventions, skill placement, and the paste-in
permission/hook snippets Kimi needs because it reads neither from a project file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.agents.backends import CursorBackend, KimiBackend
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

AGENTS_MD = Path(".kimi-code") / "AGENTS.md"


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


class TestKimiRegistration:
    def test_registered_in_backends(self):
        assert "kimi" in BACKENDS
        assert "kimi" in ALL_AGENTS

    def test_resolve_selects_kimi(self):
        assert resolve_agents("kimi") == ["kimi"]


class TestKimiConventions:
    def test_conventions_land_in_kimi_home_not_root(self, repo_with_rules):
        # Root AGENTS.md belongs to Codex/Antigravity/opencode, whose nested-rule
        # layout Kimi can't read; it gets its own file instead.
        KimiBackend().emit_conventions(repo_with_rules, force=True)
        assert (repo_with_rules / AGENTS_MD).exists()
        assert not (repo_with_rules / "AGENTS.md").exists()

    def test_path_scoped_rules_are_inlined(self, repo_with_rules):
        # Kimi scans a fixed set of AGENTS.md paths with no subdirectory
        # discovery, so a nested file would never load — rules must be inline.
        KimiBackend().emit_conventions(repo_with_rules, force=True)
        agents_md = (repo_with_rules / AGENTS_MD).read_text()
        assert "snake_case" in agents_md
        assert "Pydantic validation" in agents_md
        assert "src/api/**/*.py" in agents_md
        assert not (repo_with_rules / "src" / "api" / "AGENTS.md").exists()

    def test_pre_plan_guidance_appended(self, repo_with_rules):
        # Kimi's context-injection hook lives in the user config, so the
        # guardrails ride the always-loaded conventions file instead.
        KimiBackend().emit_conventions(repo_with_rules, force=True)
        agents_md = (repo_with_rules / AGENTS_MD).read_text()
        assert read_pre_plan_guidance().rstrip() in agents_md

    def test_no_claude_md_warns_and_skips(self, repo):
        KimiBackend().emit_conventions(repo, force=True)
        assert not (repo / AGENTS_MD).exists()


class TestKimiSkills:
    def test_skills_land_in_kimi_skills_dir(self, repo_with_rules):
        ns = sanitize_skill_namespace(repo_with_rules.name)
        KimiBackend().run_skills(
            repo_with_rules, force=True, base_branch="main", review_template=None
        )
        assert (repo_with_rules / ".kimi-code" / "skills" / f"{ns}-plan" / "SKILL.md").exists()

    def test_skills_do_not_clobber_the_shared_agents_dir(self, repo_with_rules):
        # .agents/skills is also read by Kimi, but Codex and Cline already write
        # their own adapted bodies there — staying in .kimi-code avoids the fight.
        KimiBackend().run_skills(
            repo_with_rules, force=True, base_branch="main", review_template=None
        )
        assert not (repo_with_rules / ".agents").exists()


class TestKimiSettings:
    def test_permission_snippet_is_paste_in_not_live_config(self, repo):
        KimiBackend().emit_settings(repo, force=True)
        snippet = (repo / ".kimi-code" / "klaussy-permissions.toml").read_text()
        assert "~/.kimi-code/config.toml" in snippet
        # A project-local config.toml/local.toml would be ignored (or fail the
        # whole config load), so klaussy must not write one.
        assert not (repo / ".kimi-code" / "config.toml").exists()
        assert not (repo / ".kimi-code" / "local.toml").exists()

    def test_permission_rules_cover_secrets_and_stack(self, repo):
        import tomllib

        KimiBackend().emit_settings(repo, force=True)
        rules = tomllib.loads((repo / ".kimi-code" / "klaussy-permissions.toml").read_text())
        by_pattern = {r["pattern"]: r["decision"] for r in rules["permission"]["rules"]}
        assert by_pattern["Read(.env)"] == "deny"
        assert by_pattern["Read(*.pem)"] == "deny"
        # pyproject.toml in the fixture repo → the python stack is allow-listed.
        assert by_pattern["Bash(pytest *)"] == "allow"
        assert by_pattern["Bash(git *)"] == "allow"

    def test_allow_and_deny_patterns_target_different_tools(self, repo):
        # Kimi's rule-resolution order isn't documented; keeping Read() denies and
        # Bash() allows disjoint means order can't flip a decision either way.
        import tomllib

        KimiBackend().emit_settings(repo, force=True)
        rules = tomllib.loads((repo / ".kimi-code" / "klaussy-permissions.toml").read_text())
        denied = {r["pattern"] for r in rules["permission"]["rules"] if r["decision"] == "deny"}
        allowed = {r["pattern"] for r in rules["permission"]["rules"] if r["decision"] == "allow"}
        assert all(p.startswith("Read(") for p in denied)
        assert all(p.startswith("Bash(") for p in allowed)


class TestKimiHooks:
    def test_guards_installed_and_snippet_written(self, repo):
        KimiBackend().emit_hooks(repo, force=True)
        hooks_dir = repo / ".kimi-code" / "hooks"
        for guard in (
            "klaussy_read_guard.py",
            "klaussy_comment_guard.py",
            "klaussy_dependency_guard.py",
            "klaussy_self_review_guard.py",
        ):
            assert (hooks_dir / guard).exists()
        assert (repo / ".kimi-code" / "klaussy-hooks.toml").exists()

    def test_hook_entries_use_kimi_events_and_tool_names(self, repo):
        import tomllib

        KimiBackend().emit_hooks(repo, force=True)
        hooks = tomllib.loads((repo / ".kimi-code" / "klaussy-hooks.toml").read_text())["hooks"]
        events = {h["event"] for h in hooks}
        assert events == {"PreToolUse", "Stop"}
        matchers = {h.get("matcher") for h in hooks}
        # Anchored so `Read` doesn't also fire on Kimi's ReadMediaFile tool.
        assert "^Read$" in matchers
        assert "^Bash$" in matchers

    def test_hook_command_resolves_repo_root_and_no_ops_elsewhere(self, repo):
        import tomllib

        KimiBackend().emit_hooks(repo, force=True)
        hooks = tomllib.loads((repo / ".kimi-code" / "klaussy-hooks.toml").read_text())["hooks"]
        for hook in hooks:
            # The config is global, so a scaffold-time absolute path would point
            # at the wrong repo, and a bare path would error in every other one.
            assert hook["command"].startswith("klaussy-hook --repo-relative .kimi-code/hooks/")
            assert str(repo) not in hook["command"]

    def test_hook_command_is_shell_and_interpreter_agnostic(self, repo):
        # Kimi's four-field hook schema has no per-OS override (an unknown key
        # fails the whole config load), so the one command string has to run in
        # sh, cmd, and PowerShell alike — no $(), no [ -f ], no python3 token.
        import tomllib

        KimiBackend().emit_hooks(repo, force=True)
        hooks = tomllib.loads((repo / ".kimi-code" / "klaussy-hooks.toml").read_text())["hooks"]
        for hook in hooks:
            assert not any(tok in hook["command"] for tok in ("$(", "[ -f", "exec ", ";", "&&"))
            assert "python3" not in hook["command"]

    def test_self_review_guard_uses_the_kimi_dialect(self, repo):
        KimiBackend().emit_hooks(repo, force=True)
        guard = (repo / ".kimi-code" / "hooks" / "klaussy_self_review_guard.py").read_text()
        assert "DIALECT: str = 'kimi'" in guard

    def test_existing_snippet_preserved_without_force(self, repo):
        snippet = repo / ".kimi-code" / "klaussy-hooks.toml"
        snippet.parent.mkdir(parents=True)
        snippet.write_text("# hand-edited\n")
        KimiBackend().emit_hooks(repo, force=False)
        assert snippet.read_text() == "# hand-edited\n"


class TestKimiSubagentAndPlanAdaptation:
    """Kimi has real sub-agents (`Agent`/`AgentSwarm`) and a real plan mode
    (`EnterPlanMode`), so its skill banner names them instead of hedging."""

    SUBAGENT_BODY = "Use the Agent tool to launch all selected sub-agents in parallel."
    PLAN_BODY = "Enter plan mode and present findings before editing."
    GENERIC_MARKER = "Most coding agents now have their own"

    def test_subagent_banner_names_kimi_mechanism(self):
        out = adapt_body(self.SUBAGENT_BODY, KimiBackend.profile)
        assert "AgentSwarm" in out
        assert self.GENERIC_MARKER not in out

    def test_plan_banner_names_kimi_plan_mode(self):
        out = adapt_body(self.PLAN_BODY, KimiBackend.profile)
        assert "EnterPlanMode" in out
        assert "own plan/approval mode" not in out

    def test_generic_backend_still_gets_generic_banner(self):
        out = adapt_body(self.SUBAGENT_BODY, CursorBackend.profile)
        assert self.GENERIC_MARKER in out
        assert "AgentSwarm" not in out
