"""The single base-branch resolver, and the stacked detection on top.

Three implementations preceded it, two preferring `dev` over the repo's real
default. These pin the ladder so a fourth doesn't grow back.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from klaussy import base_branch, review_prep
from klaussy.cli import app


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _bare_repo(tmp_path: Path, default: str) -> Path:
    """A clone whose `origin/HEAD` points at `default`, as a real clone's does."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", default, str(origin)], check=True)

    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", default, str(seed)], check=True)
    _git(seed, "config", "user.email", "t@example.com")
    _git(seed, "config", "user.name", "t")
    _commit(seed, "seed.txt")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "-u", "origin", default)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    return work


def _local_repo(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "solo"
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _commit(repo, "seed.txt")
    return repo


# --- the ladder --------------------------------------------------------------


def test_an_explicit_base_wins_over_everything(tmp_path):
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "branch", "release")

    resolved = base_branch.resolve(repo, explicit="release", default="develop")

    assert resolved.branch == "release"
    assert resolved.source == base_branch.SOURCE_EXPLICIT


def test_the_remote_default_beats_a_stale_develop(tmp_path):
    """The regression the old order got wrong: `develop` exists, `main` is default."""
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "branch", "develop")
    _git(repo, "branch", "dev")

    resolved = base_branch.resolve(repo)

    assert resolved.branch == "main"
    assert resolved.source == base_branch.SOURCE_REMOTE_DEFAULT


def test_the_remote_default_wins_even_with_an_unusual_name(tmp_path):
    repo = _bare_repo(tmp_path, "trunk")

    assert base_branch.resolve(repo).branch == "trunk"


def test_the_scaffolded_default_is_used_when_git_has_no_remote(tmp_path):
    repo = _local_repo(tmp_path, "master")
    _git(repo, "branch", "staging")

    resolved = base_branch.resolve(repo, default="staging")

    assert resolved.branch == "staging"
    assert resolved.source == base_branch.SOURCE_SCAFFOLDED


def test_a_scaffolded_default_that_does_not_exist_is_not_used(tmp_path):
    """A base baked in months ago may name a branch this checkout never had."""
    repo = _local_repo(tmp_path, "master")

    resolved = base_branch.resolve(repo, default="gone")

    assert resolved.branch == "master"
    assert resolved.source == base_branch.SOURCE_FALLBACK


def test_a_tag_named_main_is_not_mistaken_for_a_branch(tmp_path):
    """`rev-parse --verify main` resolves a tag too, and a tag is never a base."""
    repo = _local_repo(tmp_path, "wip")
    _git(repo, "tag", "main")

    assert not base_branch.exists(repo, "main")
    assert base_branch.preferred_ref(repo, "wip") == "wip"


# --- stacked-branch detection ------------------------------------------------


def test_a_branch_cut_from_another_topic_branch_is_flagged(tmp_path):
    """feat/ui sits on feat/api, so a range against main covers feat/api's work."""
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feat/api")
    _commit(repo, "api.txt")
    _git(repo, "checkout", "-q", "-b", "feat/ui")
    _commit(repo, "ui.txt")

    resolved = base_branch.resolve(repo)

    assert resolved.branch == "main"
    assert resolved.ambiguous
    assert "feat/api" in resolved.candidates


def test_a_branch_cut_straight_from_the_base_is_not_flagged(tmp_path):
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feat/solo")
    _commit(repo, "solo.txt")

    resolved = base_branch.resolve(repo)

    assert not resolved.ambiguous, f"false positive: {resolved.candidates}"


def test_a_sibling_branch_off_the_same_base_is_not_flagged(tmp_path):
    """Two topic branches off main share main's history, and nothing more."""
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feat/other")
    _commit(repo, "other.txt")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", "feat/mine")
    _commit(repo, "mine.txt")

    resolved = base_branch.resolve(repo)

    assert not resolved.ambiguous, f"false positive: {resolved.candidates}"


def test_detection_can_be_turned_off(tmp_path):
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feat/api")
    _commit(repo, "api.txt")
    _git(repo, "checkout", "-q", "-b", "feat/ui")
    _commit(repo, "ui.txt")

    assert base_branch.resolve(repo, detect_stacked=False).candidates == ()


# --- ref preference ----------------------------------------------------------


def test_the_remote_copy_of_the_base_is_preferred(tmp_path):
    """A local base that hasn't been pulled gives a range full of merged work."""
    repo = _bare_repo(tmp_path, "main")

    assert base_branch.preferred_ref(repo, "main") == "origin/main"


def test_a_local_only_base_still_resolves(tmp_path):
    repo = _local_repo(tmp_path, "master")

    assert base_branch.preferred_ref(repo, "master") == "master"


def test_a_base_that_exists_nowhere_has_no_ref(tmp_path):
    repo = _local_repo(tmp_path, "master")

    assert base_branch.preferred_ref(repo, "nope") is None


def test_review_prep_no_longer_prefers_dev_over_the_real_default(tmp_path):
    """The live bug: review-prep and split-prep shared a dev-first detector."""
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "branch", "dev")

    assert review_prep._detect_base(repo) == "main"


# --- the CLI surface ---------------------------------------------------------


def test_klaussy_base_prints_the_branch_alone(tmp_path):
    """Printed bare so a skill can read it straight into a variable."""
    repo = _bare_repo(tmp_path, "main")
    result = CliRunner().invoke(app, ["base", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "main"


def test_klaussy_base_explain_names_the_branch_head_may_be_stacked_on(tmp_path):
    repo = _bare_repo(tmp_path, "main")
    _git(repo, "checkout", "-q", "-b", "feat/api")
    _commit(repo, "api.txt")
    _git(repo, "checkout", "-q", "-b", "feat/ui")
    _commit(repo, "ui.txt")

    result = CliRunner().invoke(app, ["base", "--repo", str(repo), "--explain"])

    assert result.exit_code == 0, result.output
    assert "feat/api" in result.output
    assert base_branch.SOURCE_REMOTE_DEFAULT in result.output
