"""restack, against a real stack of branches.

The skill hands the git mechanics to `klaussy restack` and keeps two decisions:
confirm the chain, resolve conflicts. What matters is that it drives the CLI
rather than improvising `git rebase`, and that the stack comes out with each
branch carrying only its own commit.

Costs one real agent run; see e2e_harness.py for the gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import e2e_harness as harness

SKILL = "restack"

PROMPT = (
    "Use the shop-restack skill to restack this repo's branches onto main. "
    "The chain is feat/a then feat/b then feat/c, which I confirm. Go ahead "
    "and push when it is done."
)


def _layer(repo: Path, branch: str, parent: str) -> None:
    harness.git(repo, "checkout", "-q", "-b", branch, parent)
    (repo / f"{branch.split('/')[-1]}.py").write_text(f"VALUE = '{branch}'\n")
    harness.git(repo, "add", ".")
    harness.git(repo, "commit", "-q", "-m", f"feat: {branch}")
    harness.git(repo, "push", "-q", "-u", "origin", branch)


def _build(tmp_path: Path, attempt: int) -> Path:
    root = tmp_path / f"attempt{attempt}"
    root.mkdir()
    work = root / "shop"
    work.mkdir()
    harness.git(work.parent, "init", "-q", "-b", "main", str(work))
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        harness.git(work, "config", key, value)
    (work / "CLAUDE.md").write_text("# shop\n\n## Commands\n\n```bash\npytest\n```\n")
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "chore: base")
    remote = root / "origin.git"
    harness.git(work, "init", "-q", "--bare", str(remote))
    harness.git(work, "remote", "add", "origin", str(remote))
    harness.git(work, "push", "-q", "-u", "origin", "main")

    _layer(work, "feat/a", "main")
    _layer(work, "feat/b", "feat/a")
    _layer(work, "feat/c", "feat/b")

    # The base moves under the stack, which is what a restack is for.
    harness.git(work, "checkout", "-q", "main")
    (work / "moved.py").write_text("MOVED = True\n")
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "chore: move main")
    harness.git(work, "push", "-q", "origin", "main")
    harness.git(work, "checkout", "-q", "feat/c")

    harness.install_skills(work)
    return work


def _own_commits(repo: Path, parent: str, child: str) -> int:
    return int(harness.git(repo, "rev-list", "--count", f"{parent}..{child}").stdout.strip())


def _check_one_run(repo: Path) -> None:
    calls, final = harness.run_agent(
        repo, PROMPT, path_prefix=Path(sys.executable).parent, timeout=900
    )
    joined = "\n".join(calls)
    trace = "tool calls:\n" + "\n".join(c[:200] for c in calls) + f"\nagent said:\n{final[:1200]}"

    assert "klaussy restack" in joined, f"the CLI was never used. {trace}"

    # The stack sits on the moved base, each branch carrying only its own work.
    main_tip = harness.git(repo, "rev-parse", "origin/main").stdout.strip()
    merge_base = harness.git(repo, "merge-base", "feat/a", "origin/main").stdout.strip()
    assert merge_base == main_tip, f"feat/a is not on the moved base. {trace}"
    for parent, child in (("feat/a", "feat/b"), ("feat/b", "feat/c")):
        own = _own_commits(repo, parent, child)
        assert own == 1, f"{child} carries {own} commits over {parent}, expected 1. {trace}"

    # A lease is what keeps a force-push from clobbering someone else.
    unleased = [c for c in calls if "push" in c and "--force" in c and "with-lease" not in c]
    assert not unleased, f"force-pushed without a lease: {unleased}. {trace}"


@harness.requires_e2e
def test_restacks_the_chain_through_the_cli(tmp_path: Path):
    """One retry on a fresh stack: an agent loop varies, a broken skill doesn't."""
    try:
        _check_one_run(_build(tmp_path, 1))
    except AssertionError as first:
        try:
            _check_one_run(_build(tmp_path, 2))
        except AssertionError as second:
            raise AssertionError(f"both attempts fell short.\n\nfirst:\n{first}") from second
