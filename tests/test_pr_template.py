"""The request template goes where the repo's host actually reads it."""

import subprocess
from pathlib import Path

import pytest

from klaussy import toolkit
from klaussy.forge import FORGE_BITBUCKET, FORGE_GITHUB, FORGE_GITLAB
from klaussy.pr_template import scaffold_pr_template

GITHUB_PATH = Path(".github") / "PULL_REQUEST_TEMPLATE.md"
GITLAB_PATH = Path(".gitlab") / "merge_request_templates" / "Default.md"


def _repo(path: Path, remote: str | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return path


class TestPerHost:
    def test_github_keeps_its_path(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@github.com:owner/repo.git")
        assert scaffold_pr_template(repo=repo) == repo / GITHUB_PATH
        assert (repo / GITHUB_PATH).exists()

    def test_gitlab_gets_the_merge_request_path(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@gitlab.com:group/repo.git")
        assert scaffold_pr_template(repo=repo) == repo / GITLAB_PATH
        assert (repo / GITLAB_PATH).exists()
        assert not (repo / GITHUB_PATH).exists()

    def test_bitbucket_writes_nothing(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@bitbucket.org:ws/repo.git")
        assert scaffold_pr_template(repo=repo) is None
        assert not (repo / GITHUB_PATH).exists()
        assert not (repo / GITLAB_PATH).exists()

    def test_undetected_host_falls_back_to_github(self, tmp_path: Path):
        # A repo scaffolded before its remote exists still deserves a template;
        # a stray markdown file is harmless if the fallback guesses wrong.
        repo = _repo(tmp_path)
        assert scaffold_pr_template(repo=repo) == repo / GITHUB_PATH

    def test_explicit_forge_overrides_detection(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@github.com:owner/repo.git")
        assert scaffold_pr_template(repo=repo, forge=FORGE_GITLAB) == repo / GITLAB_PATH

    def test_forge_name_is_case_insensitive(self, tmp_path: Path):
        repo = _repo(tmp_path)
        assert scaffold_pr_template(repo=repo, forge=" GitLab ") == repo / GITLAB_PATH

    def test_unknown_forge_raises_instead_of_defaulting(self, tmp_path: Path):
        # A typo must not fall through to the GitHub layout.
        repo = _repo(tmp_path, "git@gitlab.com:group/repo.git")
        with pytest.raises(ValueError, match="gitlub"):
            scaffold_pr_template(repo=repo, forge="gitlub")
        assert not (repo / GITHUB_PATH).exists()


class TestExisting:
    def test_existing_github_template_is_left_alone(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@github.com:owner/repo.git")
        (repo / ".github").mkdir()
        (repo / GITHUB_PATH).write_text("mine\n")
        assert scaffold_pr_template(repo=repo) is None
        assert (repo / GITHUB_PATH).read_text() == "mine\n"

    def test_existing_gitlab_template_under_any_name_counts(self, tmp_path: Path):
        # GitLab allows several named templates; any one of them means the repo
        # already has a convention worth not clobbering.
        repo = _repo(tmp_path, "git@gitlab.com:group/repo.git")
        (repo / ".gitlab" / "merge_request_templates").mkdir(parents=True)
        (repo / ".gitlab" / "merge_request_templates" / "Bugfix.md").write_text("mine\n")
        assert scaffold_pr_template(repo=repo) is None

    def test_force_overwrites(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@gitlab.com:group/repo.git")
        scaffold_pr_template(repo=repo)
        assert scaffold_pr_template(repo=repo, force=True) == repo / GITLAB_PATH


class TestPublicSurface:
    def test_toolkit_exposes_both_names(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@gitlab.com:group/repo.git")
        assert toolkit.pr_template(repo) == repo / GITLAB_PATH
        assert "pr_template" in toolkit.__all__

    def test_deprecated_toolkit_alias_still_works(self, tmp_path: Path):
        repo = _repo(tmp_path, "git@github.com:owner/repo.git")
        assert toolkit.github(repo) == repo / GITHUB_PATH

    def test_deprecated_module_alias_still_imports(self, tmp_path: Path):
        from klaussy.github import scaffold_github

        repo = _repo(tmp_path, "git@github.com:owner/repo.git")
        assert scaffold_github(repo=repo) == repo / GITHUB_PATH

    def test_bitbucket_constant_is_wired(self, tmp_path: Path):
        repo = _repo(tmp_path)
        assert scaffold_pr_template(repo=repo, forge=FORGE_BITBUCKET) is None
        assert scaffold_pr_template(repo=repo, forge=FORGE_GITHUB) == repo / GITHUB_PATH
