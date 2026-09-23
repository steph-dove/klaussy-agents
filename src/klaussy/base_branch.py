"""Which branch a change should be compared against, resolved at run time.

Ladder, first that applies: an explicit base; `origin/HEAD`; the scaffolded
default; a name that exists here. The forge rung ("the target of an open
request") is left to the skills, which sit above the forge adapters and pass
the answer down as `explicit`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# How the base was decided, for callers that report it back to a human.
SOURCE_EXPLICIT = "explicit"
SOURCE_REMOTE_DEFAULT = "remote-default"
SOURCE_SCAFFOLDED = "scaffolded"
SOURCE_FALLBACK = "fallback"

_LAST_RESORT = "main"


@dataclass(frozen=True)
class BaseResolution:
    """The chosen base, how it was chosen, and what might make it wrong."""

    branch: str
    source: str
    candidates: tuple[str, ...] = ()

    @property
    def ambiguous(self) -> bool:
        """True when HEAD looks cut from a branch other than this one."""
        return bool(self.candidates)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False
    )


def _out(repo: Path, *args: str) -> str:
    proc = _git(repo, *args)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def remote_default(repo: Path) -> str:
    """The branch `origin/HEAD` points at, without the remote prefix."""
    return _out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")


def exists(repo: Path, branch: str) -> bool:
    """True when `branch` is a branch here, locally or on origin.

    Checked by full ref, not bare name: `rev-parse --verify main` resolves a
    tag named main too, and a tag is never a base.
    """
    return any(
        _git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0
        for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
    )


def preferred_ref(repo: Path, branch: str) -> str | None:
    """`origin/<branch>` if present, else the local branch, else None.

    The remote copy wins, or a base nobody has pulled lately fills the range
    with already-merged commits.
    """
    for ref in (f"origin/{branch}", branch):
        if _git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return None


def fork_candidates(repo: Path, base: str) -> tuple[str, ...]:
    """Branches HEAD may have been cut from instead of `base`.

    Qualifies when HEAD's merge base with a branch is later than its merge base
    with `base`, the shape of a stack. Never picks between them: a branch cut
    *off* this one has identical extra history, so git can't tell a parent from
    a child, and guessing wrong puts someone else's commits in the diff.
    """
    base_ref = preferred_ref(repo, base)
    if base_ref is None:
        return ()
    fork = _out(repo, "merge-base", "HEAD", base_ref)
    head = _out(repo, "rev-parse", "HEAD")
    if not fork or not head:
        return ()

    current = _out(repo, "symbolic-ref", "--short", "-q", "HEAD")
    skip = {base, base_ref, current, f"origin/{current}" if current else ""}

    found: set[str] = set()
    refs = _out(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
    for ref in refs.splitlines():
        ref = ref.strip()
        if not ref or ref in skip or ref.endswith("/HEAD"):
            continue
        merge_base = _out(repo, "merge-base", "HEAD", ref)
        # Same fork point says nothing; equal to HEAD means downstream of it.
        if not merge_base or merge_base == fork or merge_base == head:
            continue
        if _git(repo, "merge-base", "--is-ancestor", fork, merge_base).returncode == 0:
            found.add(ref.removeprefix("origin/"))
    return tuple(sorted(found))


def resolve(
    repo: Path,
    *,
    explicit: str | None = None,
    default: str | None = None,
    detect_stacked: bool = True,
) -> BaseResolution:
    """Pick the base for `repo`, walking the ladder in the module docstring.

    `default` is the scaffolded base, used only once git has nothing to say.
    `detect_stacked` costs a merge base per branch; off where nobody can be
    asked anyway.
    """
    if explicit:
        branch, source = explicit, SOURCE_EXPLICIT
    elif remote := remote_default(repo):
        branch, source = remote, SOURCE_REMOTE_DEFAULT
    elif default and exists(repo, default):
        branch, source = default, SOURCE_SCAFFOLDED
    else:
        branch, source = _first_existing(repo, default), SOURCE_FALLBACK

    candidates = fork_candidates(repo, branch) if detect_stacked else ()
    return BaseResolution(branch=branch, source=source, candidates=candidates)


def _first_existing(repo: Path, default: str | None) -> str:
    """Last resort: a branch that exists, in the order one is plausibly named.

    Order matters. The old one tried `dev` first, so a repo whose default is
    `main` but which kept a stale `develop` silently picked `develop`.
    """
    for branch in ("main", "master", "develop", "dev"):
        if exists(repo, branch):
            return branch
    return default or _LAST_RESORT
