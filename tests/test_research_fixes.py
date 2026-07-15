"""Tests for the doc-accuracy fixes from the multi-agent research pass.

Covers: native nested conventions (Gemini/Codex) with the inline fallback,
the Codex settings no-op fix, the Codex hooks matcher idiom, and the Cursor
fail-closed guard hooks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from klaussy.agents.backends import (
    CodexBackend,
    CursorBackend,
    GeminiBackend,
    _rule_base_dir,
)
from klaussy.agents.hooks import codex_hooks, cursor_hooks

CLAUDE_MD = "# CLAUDE.md - demo\n\n## Conventions\n\n- snake_case\n"


def _rule(globs: list[str]) -> str:
    paths = "\n".join(f'  - "{g}"' for g in globs)
    return f"---\npaths:\n{paths}\n---\n\n# Rule body\n\n- Use pydantic\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (tmp_path / "CLAUDE.md").write_text(CLAUDE_MD)
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    return tmp_path


class TestRuleBaseDir:
    @pytest.mark.parametrize(
        "globs, expected",
        [
            (["src/api/**/*.py"], "src/api"),
            (["docs/**/*.md", "docs/**/*.mdx"], "docs"),
            (["**/*.py"], None),  # root-level wildcard → inline
            (["src/a/**", "src/b/**"], None),  # disagreeing bases → inline
            (["src/api/config.py"], None),  # wildcard-free literal → inline
        ],
    )
    def test_base_dir(self, globs, expected):
        assert _rule_base_dir(globs) == expected


class TestNestedConventions:
    def test_gemini_writes_nested_when_dir_exists(self, repo):
        (repo / "src" / "api").mkdir(parents=True)
        (repo / ".claude" / "rules" / "api.md").write_text(_rule(["src/api/**/*.py"]))
        GeminiBackend().emit_conventions(repo, force=True)
        nested = (repo / "src" / "api" / "GEMINI.md").read_text()
        assert "Use pydantic" in nested
        # Root file holds project-wide only — no inlined path-scoped section.
        assert "Path-scoped rules" not in (repo / "GEMINI.md").read_text()

    def test_codex_writes_nested_when_dir_exists(self, repo):
        (repo / "src" / "api").mkdir(parents=True)
        (repo / ".claude" / "rules" / "api.md").write_text(_rule(["src/api/**/*.py"]))
        CodexBackend().emit_conventions(repo, force=True)
        assert (repo / "src" / "api" / "AGENTS.md").exists()
        assert "Path-scoped rules" not in (repo / "AGENTS.md").read_text()

    def test_nested_rule_does_not_duplicate_generated_heading(self, repo):
        # klaussy-repo-conventions writes rule bodies that already open with a
        # "# Rules for <glob>" heading; the backend must strip it before adding
        # its own, or nested AGENTS.md/GEMINI.md ends up with a duplicate header.
        (repo / "src" / "api").mkdir(parents=True)
        rule = (
            '---\npaths:\n  - "src/api/**/*.py"\n---\n\n'
            "# Rules for `src/api/**/*.py`\n\n## Conventions\n\n- Use pydantic\n"
        )
        (repo / ".claude" / "rules" / "api.md").write_text(rule)
        GeminiBackend().emit_conventions(repo, force=True)
        nested = (repo / "src" / "api" / "GEMINI.md").read_text()
        assert nested.count("# Rules for") == 1
        assert "Use pydantic" in nested

    def test_inline_fallback_when_dir_missing(self, repo):
        # No src/api dir on disk → rule stays inlined in the root file.
        (repo / ".claude" / "rules" / "api.md").write_text(_rule(["src/api/**/*.py"]))
        GeminiBackend().emit_conventions(repo, force=True)
        assert not (repo / "src" / "api" / "GEMINI.md").exists()
        assert "Path-scoped rules" in (repo / "GEMINI.md").read_text()

    def test_inline_fallback_for_rootlevel_glob(self, repo):
        (repo / ".claude" / "rules" / "all.md").write_text(_rule(["**/*.py"]))
        GeminiBackend().emit_conventions(repo, force=True)
        assert "Path-scoped rules" in (repo / "GEMINI.md").read_text()


class TestCodexSettingsNoOp:
    def test_safety_keys_are_commented_not_active(self, repo):
        CodexBackend().emit_settings(repo, force=True)
        content = (repo / ".codex" / "config.toml").read_text()
        # approval_policy / sandbox_mode must appear only inside comments — they
        # are no-ops in a project-local config, so we never emit them as live TOML.
        for line in content.splitlines():
            if "approval_policy" in line or "sandbox_mode" in line:
                assert line.lstrip().startswith("#"), f"active no-op key: {line!r}"


class TestCodexHooksMatcher:
    def test_matcher_is_canonical_bash(self, repo):
        import json

        codex_hooks(repo, force=True)
        config = json.loads((repo / ".codex" / "hooks.json").read_text())
        matcher = config["hooks"]["PreToolUse"][0]["matcher"]
        assert matcher == "Bash"


class TestCursorFailClosed:
    def test_guard_hooks_fail_closed(self, repo):
        import json

        cursor_hooks(repo, force=True)
        hooks = json.loads((repo / ".cursor" / "hooks.json").read_text())["hooks"]
        assert hooks["beforeReadFile"][0]["failClosed"] is True
        assert hooks["beforeShellExecution"][0]["failClosed"] is True

    def test_alwaysapply_rule_has_no_description(self, repo):
        (repo / ".claude" / "rules" / "api.md").write_text(_rule(["src/api/**/*.py"]))
        CursorBackend().emit_conventions(repo, force=True)
        conventions = (repo / ".cursor" / "rules" / "conventions.mdc").read_text()
        assert "description:" not in conventions
        assert "alwaysApply: true" in conventions
