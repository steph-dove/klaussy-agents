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
