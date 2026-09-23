"""The base a skill diffs against, decided in a repo built to get it wrong.

A prompt eval cannot cover this. The harness there strips ```! blocks and
disallows every tool, so the agent has no way to run `klaussy base` and no repo
to run it against; the best such a test can show is that the skill *says* it
would resolve. This builds the repo instead and looks at the answer.

The fixture carries both ways the old behaviour failed at once. `develop` exists
but is not the default, which is what made scaffolding and review-prep pick it.
And `feat/ui` sits on `feat/api` rather than on `main`, so a range against the
default covers a whole branch of someone else's commits.

What this proves and doesn't: that the agent lands on the right base and notices
the stack. Not how it got there, deliberately. On the first real run it never
called `klaussy base` at all and worked the answer out from `git branch
--contains` instead, which is a fine way to arrive. Pinning the mechanism would
have failed a correct review. Read a failure here as "a review was scoped to the
wrong commits", which is worth catching however it happened.

Costs one real agent run; see e2e_harness.py for the gate.
"""

from __future__ import annotations

from pathlib import Path

import e2e_harness as harness

PROMPT = (
    "Review the current branch using the shop-review skill. "
    "Tell me which base branch you reviewed against before anything else."
)


def _commit(repo: Path, name: str, body: str) -> None:
    (repo / name).write_text(body)
    harness.git(repo, "add", name)
    harness.git(repo, "commit", "-q", "-m", f"feat: add {name}")


def _stacked_repo(tmp_path: Path) -> Path:
    """`feat/ui` on `feat/api` on `main`, with a stale `develop` to the side."""
    origin = tmp_path / "origin.git"
    harness.sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(origin))

    seed = tmp_path / "seed"
    harness.sh(tmp_path, "git", "init", "-q", "-b", "main", str(seed))
    harness.git(seed, "config", "user.email", "t@example.com")
    harness.git(seed, "config", "user.name", "t")
    _commit(seed, "README.md", "# shop\n")
    harness.git(seed, "remote", "add", "origin", str(origin))
    harness.git(seed, "push", "-q", "-u", "origin", "main")

    repo = tmp_path / "shop"
    harness.sh(tmp_path, "git", "clone", "-q", str(origin), str(repo))
    harness.git(repo, "config", "user.email", "t@example.com")
    harness.git(repo, "config", "user.name", "t")

    # The branch that used to win on name alone, carrying nothing of its own.
    harness.git(repo, "branch", "develop")

    harness.git(repo, "checkout", "-q", "-b", "feat/api")
    _commit(repo, "api.py", "def handler():\n    return {}\n")
    harness.git(repo, "checkout", "-q", "-b", "feat/ui")
    _commit(repo, "ui.py", "def render():\n    return '<div/>'\n")
    return repo


@harness.requires_e2e
def test_the_agent_reviews_against_the_right_base_and_sees_the_stack(tmp_path: Path):
    repo = _stacked_repo(tmp_path)
    harness.install_skills(repo, base_branch="develop")

    calls, final = harness.run_agent(repo, PROMPT)
    said = final.lower()
    ran = " ".join(calls).lower()

    assert "main" in said, f"didn't name the resolved base: {final!r}"

    # `develop` is the scaffolded base and the one the old code picked. A range
    # against it is the failure this whole change exists to stop.
    assert "develop.." not in ran, f"diffed against the stale branch: {calls}"

    # The commits under feat/api are not this branch's work. Naming it is the
    # whole point: silently including them is the bug phase 2 set out to fix.
    assert "feat/api" in said, f"reviewed a stacked branch without noticing: {final!r}"


@harness.requires_e2e
def test_the_resolver_itself_agrees_in_the_same_repo(tmp_path: Path):
    """Cheap companion: no agent, just the CLI the skill is told to run.

    Separates "the resolver is wrong" from "the agent ignored it" when the run
    above fails, which is the first question a failure raises.
    """
    repo = _stacked_repo(tmp_path)

    proc = harness.sh(repo, "klaussy", "base", "--explain")

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[0].strip() == "main"
    assert "feat/api" in proc.stdout
