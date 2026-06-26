"""The commit guard must only run format/lint commands scoped to the staged diff.

Regression coverage for the bug where a JS repo's format command resolved to a
bare `npm run format` (`prettier --write .`), reformatting the whole tree on
every commit and blocking on any unrelated failure.
"""

import json
from pathlib import Path

from klaussy.hooks import (
    PATHS_PLACEHOLDER,
    _detect_format_command,
    _detect_lint_command,
    _has_node_tool,
)


def _pkg(tmp_path: Path, data: dict) -> Path:
    (tmp_path / "package.json").write_text(json.dumps(data))
    return tmp_path


# --- format: never unscoped, never repo-wide -------------------------------


def test_format_prefers_scoped_prettier_over_npm_script(tmp_path: Path):
    repo = _pkg(tmp_path, {"scripts": {"format": "prettier --write ."}})
    cmd = _detect_format_command(repo)
    assert cmd == f"npx prettier --write --ignore-unknown {PATHS_PLACEHOLDER}"
    assert "npm run format" not in (cmd or "")


def test_format_detects_prettier_as_dependency(tmp_path: Path):
    repo = _pkg(tmp_path, {"devDependencies": {"prettier": "^3.0.0"}})
    assert _detect_format_command(repo) == (
        f"npx prettier --write --ignore-unknown {PATHS_PLACEHOLDER}"
    )


def test_format_skips_when_formatter_cannot_be_scoped(tmp_path: Path):
    # A format script with no recognizable scoped formatter must NOT fall back to
    # a repo-wide `npm run format`.
    repo = _pkg(tmp_path, {"scripts": {"format": "biome format --write ."}})
    assert _detect_format_command(repo) is None


def test_python_format_stays_scoped(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert _detect_format_command(tmp_path) == f"ruff format {PATHS_PLACEHOLDER}"


# --- lint: never unscoped, never repo-wide ---------------------------------


def test_lint_prefers_scoped_eslint_over_npm_script(tmp_path: Path):
    repo = _pkg(tmp_path, {"scripts": {"lint": "eslint ."}})
    cmd = _detect_lint_command(repo)
    assert cmd == f"npx eslint --fix {PATHS_PLACEHOLDER}"
    assert "npm run" not in (cmd or "")


def test_lint_skips_unscopable_npm_script(tmp_path: Path):
    # A `lint` script that isn't eslint can't be scoped -> skip, don't run the
    # whole tree (which would block on pre-existing issues elsewhere).
    repo = _pkg(tmp_path, {"scripts": {"lint": "tsc --noEmit", "lint:fix": "biome lint"}})
    assert _detect_lint_command(repo) is None


def test_no_detectable_stack_returns_none(tmp_path: Path):
    assert _detect_format_command(tmp_path) is None
    assert _detect_lint_command(tmp_path) is None


# --- helper ----------------------------------------------------------------


def test_has_node_tool_matches_deps_and_scripts():
    assert _has_node_tool({"devDependencies": {"eslint": "9"}}, "eslint")
    assert _has_node_tool({"dependencies": {"prettier": "3"}}, "prettier")
    assert _has_node_tool({"scripts": {"fmt": "prettier --write ."}}, "prettier")
    assert not _has_node_tool({"scripts": {"build": "tsc"}}, "prettier")
    assert not _has_node_tool({}, "eslint")
