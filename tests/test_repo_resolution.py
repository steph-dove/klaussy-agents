"""Whatever directory klaussy is pointed at, it scaffolds the repository it's in.

The namespace is the repo folder's name, so a command run in `src/deep/` used to
produce `deep-review` in that subfolder, and one run in a home directory named
every skill after the user.
"""

import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from klaussy import toolkit
from klaussy.cli import app
from klaussy.repo import git_root, resolve_repo

runner = CliRunner()


@pytest.fixture()
def nested(tmp_path: Path) -> tuple[Path, Path]:
    """A git repo named `myproject` with a `src/deep` subdirectory."""
    root = tmp_path / "myproject"
    deep = root / "src" / "deep"
    deep.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (root / "CLAUDE.md").write_text("# myproject\n\n## Conventions\n\n- **Style**: snake_case.\n")
    return root, deep


class TestResolver:
    def test_finds_the_root_from_a_subdirectory(self, nested):
        root, deep = nested
        assert git_root(deep) == root.resolve()
        assert resolve_repo(deep) == root.resolve()

    def test_falls_back_to_the_directory_outside_a_repo(self, tmp_path: Path):
        plain = tmp_path / "plainfolder"
        plain.mkdir()
        assert git_root(plain) is None
        assert resolve_repo(plain) == plain.resolve()

    def test_missing_path_is_not_an_error(self, tmp_path: Path):
        assert git_root(tmp_path / "nope") is None


class TestScaffolding:
    def test_cli_skills_land_at_the_root_with_its_name(self, nested):
        root, deep = nested
        args = ["skills", "--repo", str(deep), "-b", "main", "--agents", "claude"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.stdout
        assert (root / ".claude" / "skills" / "myproject-review" / "SKILL.md").exists()
        assert not (deep / ".claude").exists()

    def test_toolkit_skills_land_at_the_root(self, nested):
        root, deep = nested
        toolkit.skills(deep, agents="claude", base_branch="main")
        assert (root / ".claude" / "skills" / "myproject-review" / "SKILL.md").exists()

    def test_cli_checklist_writes_to_the_root(self, nested):
        root, deep = nested
        toolkit.skills(deep, agents="claude", base_branch="main")
        result = runner.invoke(app, ["checklist", "--repo", str(deep), "-b", "main", "--force"])
        assert result.exit_code == 0, result.stdout
        assert (root / ".claude" / "skills" / "myproject-review" / "SKILL.md").exists()

    def test_toolkit_uninstall_plans_against_the_root(self, nested):
        root, deep = nested
        toolkit.skills(deep, agents="claude", base_branch="main")
        assert toolkit.uninstall(deep, dry_run=True).repo == root.resolve()


class TestHereFlag:
    def test_here_scaffolds_the_subdirectory_itself(self, nested):
        # A subproject inside a bigger repo (or this repo's own examples/).
        root, deep = nested
        args = ["skills", "--repo", str(deep), "--here", "-b", "main", "--agents", "claude"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.stdout
        assert (deep / ".claude" / "skills" / "deep-review" / "SKILL.md").exists()
        assert not (root / ".claude").exists()


class TestHomeGuard:
    def test_refuses_a_home_directory_that_is_not_a_repo(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = runner.invoke(app, ["skills", "--repo", str(home)])
        assert result.exit_code == 1
        # rich wraps the message, so compare on collapsed whitespace.
        assert "home directory, not a repository" in re.sub(r"\s+", " ", result.stdout)
        assert not (home / ".claude").exists()

    def test_allows_a_home_directory_that_is_a_repo(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "dotfiles"
        home.mkdir()
        subprocess.run(["git", "init", "-q", str(home)], check=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        result = runner.invoke(app, ["skills", "--repo", str(home), "--base-branch", "main"])
        assert result.exit_code == 0, result.stdout
        assert (home / ".claude" / "skills" / "dotfiles-review" / "SKILL.md").exists()
