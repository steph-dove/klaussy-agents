from typer.testing import CliRunner

from klaussy.agents.base import build_skill_payloads
from klaussy.cli import app
from klaussy.skills import VERSION_FILE, scaffold_skills


def test_only_scaffolds_the_named_skills_and_leaves_the_version_alone(tmp_path):
    (tmp_path / ".git").mkdir()
    scaffold_skills(repo=tmp_path, base_branch="main", only=["review"])
    skills_dir = tmp_path / ".claude" / "skills"
    dirs = [p.name for p in skills_dir.iterdir() if p.is_dir()]
    assert len(dirs) == 1 and dirs[0].endswith("-review")
    assert not (skills_dir / VERSION_FILE).exists()


def test_only_narrows_the_generic_backends_payloads(tmp_path):
    (tmp_path / ".git").mkdir()
    payloads = build_skill_payloads(repo=tmp_path, base_branch="main", only=["review", "commit"])
    assert [p.skill for p in payloads] == ["review", "commit"]


def test_skills_cli_rejects_an_unknown_skill(tmp_path):
    (tmp_path / ".git").mkdir()
    result = CliRunner().invoke(
        app, ["skills", "--repo", str(tmp_path), "-b", "main", "--only", "reveiw"]
    )
    assert result.exit_code != 0 and "unknown skill" in result.output
