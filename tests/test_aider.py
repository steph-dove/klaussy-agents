"""Tests for the Aider backend.

Aider has no skills or hooks mechanism, so the backend emits only a flat
`CONVENTIONS.md` plus a `.aider.conf.yml` (with `read:` wiring, lint/test
gating) and an `.aiderignore`. These tests validate that surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.agents.backends import AiderBackend

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


# --- registration ------------------------------------------------------------


def test_aider_registered():
    assert "aider" in ALL_AGENTS
    assert isinstance(BACKENDS["aider"], AiderBackend)
    assert resolve_agents("aider") == ["aider"]


# --- conventions -------------------------------------------------------------


def test_conventions_inlines_project_wide_and_scoped_rules(repo_with_rules: Path):
    AiderBackend().emit_conventions(repo_with_rules, force=False)
    conv = repo_with_rules / "CONVENTIONS.md"
    assert conv.exists()
    text = conv.read_text()
    # Project-wide content is present...
    assert "snake_case" in text
    # ...and path-scoped rules are inlined (aider has no nested/glob loading).
    assert "Pydantic validation" in text
    assert "src/api/**/*.py" in text


def test_conventions_warns_without_claude_md(repo: Path):
    AiderBackend().emit_conventions(repo, force=False)
    assert not (repo / "CONVENTIONS.md").exists()


# --- settings ----------------------------------------------------------------


def test_settings_writes_conf_and_ignore(repo: Path):
    AiderBackend().emit_settings(repo, force=False)

    conf = repo / ".aider.conf.yml"
    assert conf.exists()
    text = conf.read_text()
    # Conventions are wired in read-only.
    assert "read:" in text
    assert "- CONVENTIONS.md" in text
    # Secret exclusion is referenced and written.
    assert "aiderignore: .aiderignore" in text
    assert (repo / ".aiderignore").exists()
    # Ollama is offered as a commented model example (origin of the feature).
    assert "ollama_chat/" in text


def test_settings_maps_python_stack_to_lint_and_test(repo: Path):
    AiderBackend().emit_settings(repo, force=False)
    text = (repo / ".aider.conf.yml").read_text()
    assert "auto-lint: true" in text
    assert "python: ruff check" in text
    assert "test-cmd: pytest" in text


def test_settings_omits_lint_test_without_known_stack(tmp_path: Path):
    # No pyproject/package.json/etc -> no lint-cmd/test-cmd lines.
    AiderBackend().emit_settings(tmp_path, force=False)
    text = (tmp_path / ".aider.conf.yml").read_text()
    assert "lint-cmd:" not in text
    assert "test-cmd:" not in text
    # The conventions wiring is still present.
    assert "- CONVENTIONS.md" in text


def test_settings_maps_node_stack(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "x"}\n')
    AiderBackend().emit_settings(tmp_path, force=False)
    text = (tmp_path / ".aider.conf.yml").read_text()
    assert "javascript: npx eslint" in text
    assert "test-cmd: npm test" in text


# --- skills / hooks are intentionally not emitted ----------------------------


def test_run_skills_emits_nothing(repo_with_rules: Path):
    backend = AiderBackend()
    backend.run_skills(repo_with_rules, force=False, base_branch="main", review_template=None)
    # No skills directory of any kind is created.
    assert not (repo_with_rules / ".aider").exists()
    assert not (repo_with_rules / ".agents" / "skills").exists()


def test_emit_hooks_emits_nothing(repo: Path):
    AiderBackend().emit_hooks(repo, force=False)
    assert not (repo / ".aider.conf.yml").exists()  # hooks step writes nothing


# --- full step list ----------------------------------------------------------


def test_steps_produce_only_conventions_and_settings(repo_with_rules: Path):
    backend = AiderBackend()
    for _label, fn in backend.steps(
        repo_with_rules, force=True, base_branch="main", review_template=None
    ):
        fn()
    assert (repo_with_rules / "CONVENTIONS.md").exists()
    assert (repo_with_rules / ".aider.conf.yml").exists()
    assert (repo_with_rules / ".aiderignore").exists()
