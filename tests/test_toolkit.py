"""Tests for the public library surface (klaussy.toolkit)."""

from pathlib import Path

import pytest

from klaussy import toolkit
from klaussy.toolkit import ScaffoldResult

SAMPLE_CLAUDE_MD = "# test\n\n## Project Overview\n\nA test project.\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "CLAUDE.md").write_text(SAMPLE_CLAUDE_MD)
    return tmp_path


def test_public_surface_is_importable():
    for name in toolkit.__all__:
        assert hasattr(toolkit, name), name


def test_humanize_strips_ai_tells():
    assert toolkit.humanize("A great solution — it works.") == "A great solution, it works."


def test_humanize_files_check_does_not_write(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("A great solution — it works.")
    changed = toolkit.humanize_files([f], check=True)
    assert changed[str(f)] is True
    assert f.read_text() == "A great solution — it works."  # untouched


def test_humanize_files_write_rewrites_in_place(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("A great solution — it works.")
    toolkit.humanize_files([f], write=True)
    assert f.read_text() == "A great solution, it works."


def test_status_covers_every_skill(repo: Path):
    report = toolkit.status(repo)
    # CLAUDE.md + settings + one row per canonical skill.
    assert len(report) == 2 + len(toolkit.SKILL_NAMES)
    assert report["CLAUDE.md"] == "exists"
    assert any("precommit" in key for key in report)
    assert any("humanize" in key for key in report)


def test_skills_scaffold_returns_result_and_writes_files(repo: Path):
    result = toolkit.skills(repo, agents=["claude"], base_branch="main")
    assert isinstance(result, ScaffoldResult)
    assert result.ok
    assert result.agents == ["claude"]
    assert "[claude] skills" in result.completed
    # repo name is normalized into the skill dir; match by suffix, not exact name.
    fix_dirs = list((repo / ".claude" / "skills").glob("*-fix"))
    assert fix_dirs and (fix_dirs[0] / "SKILL.md").exists()


def test_skills_narrows_to_selected_agent(repo: Path):
    toolkit.skills(repo, agents=["claude"], base_branch="main")
    # Only the claude target was requested — no gemini output.
    assert not (repo / ".gemini").exists()


def test_unknown_agent_raises(repo: Path):
    with pytest.raises(ValueError, match="Unknown agent"):
        toolkit.skills(repo, agents=["bogus"])


def test_settings_scaffolds_then_rerun_marks_skipped(repo: Path):
    first = toolkit.settings(repo, agents=["claude"])
    assert first.ok and "[claude] settings" in first.completed
    assert (repo / ".claude" / "settings.json").exists()
    # Re-running without force makes the generator bail → recorded as skipped.
    again = toolkit.settings(repo, agents=["claude"])
    assert not again.ok
    assert "[claude] settings" in again.skipped


def test_hooks_scaffolds_guards(repo: Path):
    result = toolkit.hooks(repo, agents=["claude"])
    assert result.ok
    assert (repo / ".claude" / "hooks" / "comment_guard.py").exists()


def test_claude_hook_commands_are_os_aware_and_quoted():
    # A hardcoded `python3` no-ops on a Windows checkout (python.org exposes
    # `python`); and an unquoted path breaks when the project dir has spaces.
    import sys

    from klaussy import hooks

    expected_py = "python" if sys.platform == "win32" else "python3"
    assert hooks.HOOK_PY == expected_py
    for command in (
        hooks.GUARD_COMMAND,
        hooks.COMMIT_GUARD_COMMAND,
        hooks.SELF_REVIEW_GUARD_COMMAND,
    ):
        assert command.startswith(f'{expected_py} "')  # OS-aware interpreter
        assert command.endswith('.py"')  # script path is quoted (spaces-safe)


def test_github_creates_then_skips(repo: Path):
    path = toolkit.github(repo)
    assert path is not None and path.exists()
    assert toolkit.github(repo) is None  # already exists → no overwrite


def test_checklist_returns_written_path(repo: Path):
    toolkit.skills(repo, agents=["claude"], base_branch="main")  # review skill first
    # force=True to re-enrich the existing review skill (the init flow does the same).
    out = toolkit.checklist(repo, force=True, base_branch="main")
    assert out.exists()


def test_fix_and_test_skills_scope_to_base_branch(repo: Path):
    toolkit.skills(repo, agents=["claude"], base_branch="develop")
    skills_dir = repo / ".claude" / "skills"
    fix = next(skills_dir.glob("*-fix")) / "SKILL.md"
    test = next(skills_dir.glob("*-test")) / "SKILL.md"
    # fix/test scope to the branch diff, not the whole repo (substitution applied).
    assert "develop...HEAD" in fix.read_text()
    assert "develop...HEAD" in test.read_text()
