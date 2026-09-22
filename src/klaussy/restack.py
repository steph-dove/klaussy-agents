"""Deterministic restack: map a stack of branches from git ancestry, rebase it
bottom-up with `--onto`, verify, and push with a lease.

The restack skill used to drive all of this one git command per model turn,
including an ancestry check for every ordered pair of branches. None of it needs
judgment except confirming the chain and resolving conflicts, so the mechanics
live here and the skill keeps only those two decisions.

State for an in-progress run is written under the git dir (per worktree, never
committed), so `run --continue` can pick up after a conflict and `undo` can put
every branch back where it started.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

PARENT_KEY = "klaussyparent"
STATE_FILE = "klaussy-restack.json"


class RestackError(RuntimeError):
    """A precondition failed; the message says what to do about it."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RestackError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def _out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def _ok(repo: Path, *args: str) -> bool:
    return _git(repo, *args, check=False).returncode == 0


def resolve_base(repo: Path, base: str | None) -> str:
    """The ref to restack onto: `origin/<base>` when it exists, else `<base>`."""
    if base is None:
        head = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
        if head.returncode == 0:
            return head.stdout.strip()
        base = "main"
    for ref in (f"origin/{base}", base):
        if _ok(repo, "rev-parse", "--verify", "--quiet", ref):
            return ref
    raise RestackError(f"base branch {base!r} not found locally or on origin")


def _state_path(repo: Path) -> Path:
    return (repo / _out(repo, "rev-parse", "--git-path", STATE_FILE)).resolve()


def _rebase_in_progress(repo: Path) -> bool:
    return any(
        (repo / _out(repo, "rev-parse", "--git-path", d)).exists()
        for d in ("rebase-merge", "rebase-apply")
    )


def _clean(repo: Path) -> bool:
    return not _out(repo, "status", "--porcelain")


# --- plan --------------------------------------------------------------------


@dataclass
class Branch:
    name: str
    tip: str
    parent: str | None  # a branch name, or None when it sits on the base
    ahead: int
    boundary: str | None = None  # the parent commit this branch was built on
    landed: str | None = None  # "ancestry" | "squash" when already in the base
    authors: list[str] = field(default_factory=list)


@dataclass
class Plan:
    base: str
    base_tip: str
    branches: list[Branch]  # parents before children
    clean: bool
    fetch_failed: bool = False
    squash_check_failed: bool = False
    aliases: list[list[str]] = field(default_factory=list)
    forks: dict[str, list[str]] = field(default_factory=dict)


def _local_branches(repo: Path) -> dict[str, str]:
    lines = _out(repo, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads")
    return dict(line.split(" ", 1) for line in lines.splitlines() if line)


def _recorded_parents(repo: Path) -> dict[str, str]:
    proc = _git(repo, "config", "--get-regexp", rf"^branch\..*\.{PARENT_KEY}$", check=False)
    parents = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition(" ")
        parents[key[len("branch.") : -len(f".{PARENT_KEY}")]] = value.strip()
    return parents


def _landed(repo: Path, base: str, branch: str) -> tuple[str | None, bool]:
    """Return (how it landed, whether the squash check could run at all)."""
    if _ok(repo, "merge-base", "--is-ancestor", branch, base):
        return "ancestry", True
    # Squash and rebase merges rewrite the SHAs, so compare trees instead.
    merged = _git(repo, "merge-tree", "--write-tree", base, branch, check=False)
    if merged.returncode == 0:
        tree = merged.stdout.splitlines()[0].strip()
        if tree == _out(repo, "rev-parse", f"{base}^{{tree}}"):
            return "squash", True
    # 1 is a real conflict, so the branch hasn't landed. Anything else means the
    # command didn't run: `--write-tree` needs git 2.38, older git exits 129.
    return None, merged.returncode in (0, 1)


def _fork_point(repo: Path, parent: str, child: str) -> str | None:
    """The commit `child` was built on, searched through `parent`'s reflog.

    Plain ancestry loses the relationship once the parent is amended or
    rebased; the reflog still has the old tip the child grew from.
    """
    proc = _git(repo, "merge-base", "--fork-point", parent, child, check=False)
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def plan_restack(repo: Path | str = ".", base: str | None = None, fetch: bool = True) -> Plan:
    """Map the stack. Read-only apart from the optional fetch."""
    repo = Path(repo).resolve()
    fetch_failed = False
    if fetch:
        # A failed fetch means every comparison below runs against stale refs.
        fetch_failed = _git(repo, "fetch", "--all", "--prune", check=False).returncode != 0
    base_ref = resolve_base(repo, base)
    base_name = base_ref.removeprefix("origin/")
    tips = {n: t for n, t in _local_branches(repo).items() if n != base_name}

    ahead = {n: int(_out(repo, "rev-list", "--count", f"{base_ref}..{n}")) for n in tips}
    checks = {n: _landed(repo, base_ref, n) for n in tips}
    landed = {n: how for n, (how, _) in checks.items()}
    squash_check_failed = not all(ok for _, ok in checks.values())
    # A branch fully merged by ancestry has nothing left to move, so it only
    # matters as a parent; a squash-landed one still carries its old commits.
    stack = [n for n in tips if ahead[n] > 0]

    by_tip: dict[str, list[str]] = {}
    for n in stack:
        by_tip.setdefault(tips[n], []).append(n)
    aliases = [sorted(v) for v in by_tip.values() if len(v) > 1]

    recorded = _recorded_parents(repo)
    parents: dict[str, str | None] = {}
    boundary: dict[str, str | None] = {}
    for n in stack:
        rec = recorded.get(n)
        # A recorded parent that has since fully landed no longer anchors anything.
        if rec in stack and rec != n:
            parents[n] = rec
            boundary[n] = _fork_point(repo, rec, n) or _out(repo, "merge-base", rec, n)
            continue
        # Nearest branch this one grew from, counting old tips from the reflog.
        # A fork point already in the base is where both left the base, not a parent.
        candidates = {}
        for a in stack:
            if a == n or tips[a] == tips[n]:
                continue
            # A descendant's reflog starts at our tip, which would read as a fork.
            if _ok(repo, "merge-base", "--is-ancestor", n, a):
                continue
            fp = _fork_point(repo, a, n)
            if fp and not _ok(repo, "merge-base", "--is-ancestor", fp, base_ref):
                candidates[a] = fp
        nearest = max(
            candidates,
            key=lambda a: int(_out(repo, "rev-list", "--count", f"{base_ref}..{candidates[a]}")),
            default=None,
        )
        parents[n] = nearest
        boundary[n] = candidates.get(nearest) if nearest else None

    children: dict[str, list[str]] = {}
    for n, p in parents.items():
        if p:
            children.setdefault(p, []).append(n)
    forks = {p: sorted(c) for p, c in children.items() if len(c) > 1}

    ordered: list[str] = []
    seen: set[str] = set()

    def visit(n: str) -> None:
        if n in seen:
            return
        seen.add(n)
        p = parents.get(n)
        if p in parents:
            visit(p)
        ordered.append(n)

    for n in sorted(stack, key=lambda n: ahead[n]):
        visit(n)

    branches = []
    for n in ordered:
        p = parents[n]
        since = boundary[n] or base_ref
        authors = _out(repo, "log", f"{since}..{n}", "--format=%an").splitlines()
        branches.append(
            Branch(
                name=n,
                tip=tips[n],
                parent=p,
                ahead=ahead[n],
                boundary=boundary[n],
                landed=landed[n],
                authors=sorted(set(authors)),
            )
        )
    return Plan(
        base=base_ref,
        base_tip=_out(repo, "rev-parse", base_ref),
        branches=branches,
        clean=_clean(repo),
        fetch_failed=fetch_failed,
        squash_check_failed=squash_check_failed,
        aliases=aliases,
        forks=forks,
    )


def render_plan(plan: Plan) -> str:
    lines = [f"Base: {plan.base} ({plan.base_tip[:7]})", ""]
    if plan.fetch_failed:
        lines.append("WARNING: `git fetch` failed, so these refs may be stale. Fix that first.")
        lines.append("")
    if plan.squash_check_failed:
        lines.append(
            "WARNING: `git merge-tree --write-tree` didn't run (it needs git 2.38), so a "
            "squash-merged branch won't be spotted. Check the bottom of the stack by hand."
        )
        lines.append("")
    if not plan.branches:
        lines.append("No branches ahead of the base: nothing to restack.")
        return "\n".join(lines) + "\n"
    for b in plan.branches:
        note = f" [landed: {b.landed}]" if b.landed else ""
        lines.append(f"  {b.parent or plan.base} -> {b.name} ({b.tip[:7]}, {b.ahead} ahead){note}")
    lines.append("")
    authors = sorted({a for b in plan.branches for a in b.authors})
    lines.append(f"Authors in the stack: {', '.join(authors) or 'none'}")
    if not plan.clean:
        lines.append("BLOCKED: the working tree is dirty. Commit or stash before running.")
    for group in plan.aliases:
        lines.append(f"ASK: {' and '.join(group)} point at the same commit; which is the parent?")
    for parent, kids in plan.forks.items():
        lines.append(f"NOTE: {parent} has several children ({', '.join(kids)}); each rebases.")
    chain = ",".join(b.name for b in plan.branches)
    lines.append("")
    lines.append(f"After the user confirms: klaussy restack run --chain {chain}")
    return "\n".join(lines) + "\n"


# --- run ---------------------------------------------------------------------


@dataclass
class RunState:
    base: str
    original: str  # branch to return to, or a SHA when detached
    order: list[str]
    parent: dict[str, str | None]
    boundary: dict[str, str | None]  # old parent commit each branch's own work starts after
    old_tip: dict[str, str]
    landed: list[str]
    done: list[str] = field(default_factory=list)
    current: str | None = None
    warnings: list[str] = field(default_factory=list)
    new_base: dict[str, str] = field(default_factory=dict)  # what each branch was put onto


def _save(repo: Path, state: RunState) -> None:
    _state_path(repo).write_text(json.dumps(asdict(state), indent=2))


def load_state(repo: Path | str = ".") -> RunState:
    repo = Path(repo).resolve()
    path = _state_path(repo)
    if not path.exists():
        raise RestackError("no restack in progress (run `klaussy restack run --chain ...` first)")
    return RunState(**json.loads(path.read_text()))


def start_run(
    repo: Path | str, chain: list[str], base: str | None = None, fetch: bool = True
) -> RunState:
    """Validate the confirmed chain against a fresh plan and record the undo point."""
    repo = Path(repo).resolve()
    if _state_path(repo).exists():
        raise RestackError("a restack is already in progress: `--continue` it or `undo` it")
    if _rebase_in_progress(repo):
        raise RestackError("a git rebase is already in progress; finish or abort it first")
    if not _clean(repo):
        raise RestackError("the working tree is dirty; commit or stash first")
    plan = plan_restack(repo, base, fetch=fetch)
    if plan.fetch_failed:
        raise RestackError(
            "`git fetch` failed, so the base and landed checks would run against stale "
            "refs. Fix the fetch, or pass --no-fetch if you meant to work offline."
        )
    known = {b.name: b for b in plan.branches}
    unknown = [n for n in chain if n not in known]
    if unknown:
        raise RestackError(f"not in the stack ahead of {plan.base}: {', '.join(unknown)}")
    for i, n in enumerate(chain):
        p = known[n].parent
        if p is not None and p not in chain[:i]:
            raise RestackError(f"{n}'s parent {p} must come before it in --chain")
    head = _git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    state = RunState(
        base=plan.base,
        original=head.stdout.strip() or _out(repo, "rev-parse", "HEAD"),
        order=chain,
        parent={n: known[n].parent for n in chain},
        boundary={n: known[n].boundary for n in chain},
        old_tip={n: known[n].tip for n in chain},
        landed=[n for n in chain if known[n].landed],
    )
    _save(repo, state)
    return state


def advance(repo: Path | str = ".") -> RunState:
    """Rebase every remaining branch; stop at the first conflict with state saved."""
    repo = Path(repo).resolve()
    state = load_state(repo)
    if state.current:
        if _rebase_in_progress(repo):
            raise RestackError(
                f"{state.current} is still mid-rebase: resolve, `git add`, "
                "`git rebase --continue`, then run this again"
            )
        if not _ok(
            repo, "merge-base", "--is-ancestor", state.new_base[state.current], state.current
        ):
            raise RestackError(
                f"{state.current} isn't on its new base (was the rebase aborted?). "
                "Run `klaussy restack undo`, or rebase it by hand and continue."
            )
        state.done.append(state.current)
        state.current = None
        _save(repo, state)

    for n in state.order:
        if n in state.done or n in state.landed:
            continue
        p = state.parent[n]
        if p is None:
            onto, upstream = state.base, state.base
        elif p in state.landed:
            # Replay only this branch's own commits: the landed parent's are in the base.
            onto, upstream = state.base, state.boundary[n]
        else:
            onto, upstream = _out(repo, "rev-parse", p), state.boundary[n]
        state.current = n
        state.new_base[n] = onto
        _save(repo, state)
        proc = _git(repo, "rebase", "--onto", onto, upstream, n, check=False)
        if proc.returncode != 0:
            if _rebase_in_progress(repo):
                return state  # conflict: the caller reports it
            raise RestackError(f"rebase of {n} failed: {proc.stderr.strip()}")
        state.done.append(n)
        state.current = None
        _save(repo, state)

    _record_parents(repo, state)
    _restore_branch(repo, state)
    _save(repo, state)
    return state


def _restore_branch(repo: Path, state: RunState) -> None:
    """Return to the branch we started on, saying so when we can't."""
    proc = _git(repo, "checkout", "--quiet", state.original, check=False)
    if proc.returncode != 0:
        state.warnings.append(f"could not check out {state.original} again: {proc.stderr.strip()}")


def _record_parents(repo: Path, state: RunState) -> None:
    """Remember the chain so the next run is deterministic and forge-free."""
    for n in state.order:
        if n in state.landed:
            continue
        p = state.parent[n]
        if p and p not in state.landed:
            _git(repo, "config", f"branch.{n}.{PARENT_KEY}", p)
        else:
            _git(repo, "config", "--unset", f"branch.{n}.{PARENT_KEY}", check=False)


def conflicted_files(repo: Path | str = ".") -> list[str]:
    return _out(Path(repo), "diff", "--name-only", "--diff-filter=U").splitlines()


def undo(repo: Path | str = ".") -> RunState:
    """Put every branch back on its recorded tip and forget the run."""
    repo = Path(repo).resolve()
    state = load_state(repo)
    if _rebase_in_progress(repo):
        _git(repo, "rebase", "--abort")
    if not _clean(repo):
        raise RestackError("the working tree is dirty; commit or stash before undoing")
    _git(repo, "checkout", "--quiet", "--detach")
    for n, sha in state.old_tip.items():
        _git(repo, "update-ref", f"refs/heads/{n}", sha)
    # Warnings from an earlier `advance` are already in the state; only a new one
    # means this undo left the worktree somewhere unexpected.
    before = len(state.warnings)
    _restore_branch(repo, state)
    _state_path(repo).unlink()
    if len(state.warnings) > before:
        raise RestackError(
            f"branches restored to their pre-restack tips, but {state.warnings[-1]}; "
            "you are on a detached HEAD"
        )
    return state


# --- verify and push ---------------------------------------------------------


@dataclass
class Check:
    branch: str
    own_commits_before: int
    own_commits_after: int
    changed: list[str]  # range-diff lines whose commit content differs

    @property
    def ok(self) -> bool:
        return self.own_commits_before == self.own_commits_after and not self.changed


def verify(repo: Path | str = ".") -> list[Check]:
    """Each branch carries exactly its own commits, unchanged by the move."""
    repo = Path(repo).resolve()
    state = load_state(repo)
    checks = []
    for n in state.done:
        p = state.parent[n]
        if p is None:
            old_upstream = _out(repo, "merge-base", state.old_tip[n], state.base)
        else:
            old_upstream = state.boundary[n]
        new_upstream = state.new_base[n]
        before = int(_out(repo, "rev-list", "--count", f"{old_upstream}..{state.old_tip[n]}"))
        after = int(_out(repo, "rev-list", "--count", f"{new_upstream}..{n}"))
        diff = _out(
            repo,
            "range-diff",
            "--no-color",
            f"{old_upstream}..{state.old_tip[n]}",
            f"{new_upstream}..{n}",
        )
        # Commit-pair lines start at column 0; the indented lines below a `!` are its diff.
        pairs = [line for line in diff.splitlines() if line and not line[0].isspace()]
        changed = [line for line in pairs if line.split()[2:3] in (["!"], ["<"], [">"])]
        checks.append(Check(n, before, after, changed))
    return checks


def push(repo: Path | str = ".", remote: str = "origin") -> list[tuple[str, bool, str]]:
    """Force-push each rebased branch bottom-up with a lease; stop at the first refusal."""
    repo = Path(repo).resolve()
    state = load_state(repo)
    base_name = state.base.removeprefix(f"{remote}/")
    results = []
    for n in state.done:
        if n == base_name:
            continue  # never force-push the base
        proc = _git(
            repo, "push", "--force-with-lease", "--force-if-includes", remote, n, check=False
        )
        results.append((n, proc.returncode == 0, proc.stderr.strip()))
        if proc.returncode != 0:
            break
    else:
        _state_path(repo).unlink()
    return results
