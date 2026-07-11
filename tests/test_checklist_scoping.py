"""Verification-command block stays diff-scoped and drops non-command noise."""

from klaussy.checklist import _build_command_checks, _strip_repo_paths


def test_strip_repo_paths_drops_trailing_tree_args():
    assert _strip_repo_paths("ruff check src/ tests/") == "ruff check"
    assert _strip_repo_paths("ruff format --check src/ tests/") == "ruff format --check"
    assert _strip_repo_paths("go test ./...") == "go test"
    assert _strip_repo_paths("ruff check --fix .") == "ruff check --fix"


def test_strip_repo_paths_keeps_flags_and_values():
    # A flag value that isn't a path must not be mistaken for one.
    assert _strip_repo_paths("eslint --max-warnings 0") == "eslint --max-warnings 0"
    assert _strip_repo_paths("pytest") == "pytest"


def test_command_block_is_scoped_to_changed_files():
    block = _build_command_checks(["ruff check src/ tests/"])
    assert "files this PR changed" in block
    assert "not the whole repo" in block
    # Path args stripped so the reviewer re-scopes to the diff.
    assert "- `ruff check`" in block
    assert "src/ tests/" not in block


def test_fenced_commands_filtered_to_verification_gates():
    # Real klaussy CLAUDE.md lists commands in a fenced block (no backticks).
    commands = [
        'pip install -e ".[dev]"',  # install → dropped
        "python -m build",  # build → dropped
        "pytest",  # verifier → kept
        "ruff check src/ tests/",  # lint → kept, scoped
        "klaussy --help",  # not a check → dropped
    ]
    block = _build_command_checks(commands)
    assert "- `pytest`" in block
    assert "- `ruff check`" in block
    assert "pip install" not in block
    assert "klaussy --help" not in block


def test_bare_tool_mentions_from_prose_bullets_are_dropped():
    # Notes bullets often mention a tool in backticks as prose, not as a runnable
    # command; a bare `ruff` isn't a check and must not leak into the block.
    bullets = [
        "- `ruff` is configured with line-length 100",
        "- ignores are declared via `# noqa` comments",
        "- No mypy configured — type hints are not enforced",
    ]
    assert _build_command_checks(bullets) == ""


def test_empty_when_no_verification_commands():
    assert _build_command_checks([]) == ""
    assert _build_command_checks(["- **Install**: `pip install -e .`"]) == ""
