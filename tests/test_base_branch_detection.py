"""The base branch is baked into twelve skills at scaffold time, so a wrong
guess here follows the user around until they re-scaffold. These pin the order
of sources: what the remote calls default wins over any name we recognize.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from klaussy.cli import _detect_base_branch


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _repo(tmp_path: Path, default: str) -> Path:
    """A clone whose origin/HEAD points at `default`, as a real clone's would."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", default, str(origin)], check=True)

    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", default, str(seed)], check=True)
    _git(seed, "config", "user.email", "t@example.com")
    _git(seed, "config", "user.name", "t")
    (seed / "README.md").write_text("x\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "-u", "origin", default)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    return work


def test_prefers_the_remote_default_over_a_stale_develop(tmp_path):
    """The regression: `develop` exists but `main` is what origin calls default."""
    repo = _repo(tmp_path, "main")
    _git(repo, "branch", "develop")
    _git(repo, "branch", "dev")

    assert _detect_base_branch(repo) == "main"


def test_uses_the_remote_default_even_when_it_is_an_unusual_name(tmp_path):
    repo = _repo(tmp_path, "trunk")

    assert _detect_base_branch(repo) == "trunk"


def test_falls_back_to_a_known_name_without_a_remote(tmp_path):
    repo = tmp_path / "solo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")

    assert _detect_base_branch(repo) == "master"


def test_returns_none_when_nothing_recognizable_exists(tmp_path):
    repo = tmp_path / "odd"
    subprocess.run(["git", "init", "-q", "-b", "wip", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")

    assert _detect_base_branch(repo) is None


def test_a_tag_named_main_is_not_mistaken_for_the_base(tmp_path):
    """`rev-parse --verify main` resolves a tag too, which would pick a ref that
    can never be a diff base."""
    repo = tmp_path / "tagged"
    subprocess.run(["git", "init", "-q", "-b", "wip", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "tag", "main")

    assert _detect_base_branch(repo) is None
