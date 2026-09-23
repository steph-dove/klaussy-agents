"""Work out which branch a change should be compared against, at run time.

The base is substituted into the skills at scaffold time, which stops being
true the moment a branch is cut from another topic branch: the diff range then
covers commits the change never added, and nothing says so. This resolves it
against the repo in front of us instead, and reports how it decided so a caller
can say which base it used.

The ladder, first that applies: an explicit base; the remote's default branch
(`origin/HEAD`); the scaffolded default the caller passes; `main`.

One rung is deliberately missing: "the target of an existing request for this
branch". Reading that needs the forge CLI, and putting a network round trip and
a `gh auth` dependency underneath every diff range is a bad trade this low in
the stack. The skills sit above the forge adapters, so they ask there and pass
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

    Checked against `refs/heads` and `refs/remotes` rather than by bare name:
    `rev-parse --verify main` resolves a *tag* named main just as happily, and
    a tag can never be the thing a branch was cut from.
    """
    return any(
        _git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0
        for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
    )


def preferred_ref(repo: Path, branch: str) -> str | None:
    """`origin/<branch>` when the repo has it, else the local branch, else None.

    The remote copy wins: a local base that hasn't been pulled in a week gives a
    diff range full of other people's already-merged commits.
    """
    for ref in (f"origin/{branch}", branch):
        if _git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return None


def fork_candidates(repo: Path, base: str) -> tuple[str, ...]:
    """Branches HEAD may have been cut from instead of `base`.

    A branch qualifies when HEAD's merge base with it is strictly later than
    HEAD's merge base with `base`: HEAD shares history with that branch which
    the base doesn't have, which is the shape of a stack.

    This does not try to pick one, and it isn't only parents. A branch cut *off*
    this one shares exactly the same extra history, so git cannot tell a parent
    from a child here, and a wrong pick puts someone else's commits in the diff.
    Detecting that the question exists is the useful part; the caller asks.
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
        # Same fork point: cut from the same place, so it says nothing about HEAD.
        # Equal to HEAD: that branch contains this one, so it's downstream, not a base.
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
    `detect_stacked` runs a merge base per branch, so turn it off where the
    answer is already known to be right and the repo is large.
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
    """Last resort: a branch that's actually here, in the order one is likely.

    Ordered by what a default branch is plausibly called. The old order put
    `dev` and `develop` first, so a repo whose default is `main` but which still
    carries a stale `develop` picked `develop` and never said so.
    """
    for branch in ("main", "master", "develop", "dev"):
        if exists(repo, branch):
            return branch
    return default or _LAST_RESORT
