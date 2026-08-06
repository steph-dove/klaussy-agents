"""Opt-in evals for the restack skill.

A restack is destructive and hard to undo, so the properties worth pinning are
the ones that decide whether history survives: `--onto` off the parent's *old*
tip (a bare rebase replays the parent's commits into the child), bottom-up
order, a leased force-push, and never touching the base branch.

The fixtures are the real shape this repo's own stack had — five dependent
branches plus a second root — rather than an invented two-branch toy.

See `harness.py` for what a prompt eval does and doesn't cover.
"""

from __future__ import annotations

import re

import pytest
from harness import load_skill_body, requires_eval_env, run_skill

# The stack as `gh pr list --json number,headRefName,baseRefName` reported it,
# with the tips recorded before any rewrite (Phase 2's safety net).
STACK_CONTEXT = """\
`git status --porcelain` is empty. `git fetch --all --prune` has run.

Recorded branch tips (before any rewrite):
  main                       9f2e1a0  (origin/main has moved on: 4 new commits)
  feat/restack-skill         e460113  PR #30, base main
  feat/forge-token           b66c6b0  PR #31, base feat/restack-skill
  feat/forge-permissions     790a6a5  PR #32, base feat/forge-token
  feat/pr-template-per-host  3de0101  PR #33, base feat/forge-permissions
  feat/bitbucket-verified    e37d401  PR #34, base feat/pr-template-per-host

Ancestry (`git merge-base --is-ancestor`) agrees with those bases.
The user has confirmed the chain. Nothing has been rebased yet.
"""

MERGED_BOTTOM_CONTEXT = """\
`git status --porcelain` is empty. `git fetch --all --prune` has run.

PR #30 (feat/restack-skill) was squash-merged into main an hour ago. Its
branch tip is still e460113 locally, and `git merge-base --is-ancestor
feat/restack-skill origin/main` exits 1, but `git merge-tree --write-tree
origin/main feat/restack-skill` prints the same tree oid as
`git rev-parse origin/main^{tree}`.

Recorded tips:
  feat/restack-skill      e460113  (merged)
  feat/forge-token        b66c6b0  PR #31, base feat/restack-skill
  feat/forge-permissions  790a6a5  PR #32, base feat/forge-token

The user has confirmed the chain and wants the stack restacked onto main.
"""

SINGLE_BRANCH_CONTEXT = """\
`git status --porcelain` is empty.

  main                origin/main is 6 commits ahead
  fix/login-redirect  one commit, based directly on main, PR #12 with base main

There are no other branches. The user says their PR is out of date.
"""

PLAN_INSTRUCTION = (
    "Produce the exact git commands you would run, in order, with a one-line "
    "reason for each. Do not run anything."
)


def _commands(text: str) -> list[str]:
    """Every git/gh command mentioned in the answer, prose or fenced."""
    return [m.group(0) for m in re.finditer(r"\b(?:git|gh)\s+[^\n`]+", text)]


@requires_eval_env
class TestStackRebasePlan:
    @pytest.fixture(scope="class")
    def plan(self) -> str:
        return run_skill("restack", STACK_CONTEXT, instruction=PLAN_INSTRUCTION)

    def test_rebases_onto_the_recorded_parent_tip(self, plan: str):
        # The whole correctness of a restack: --onto <new-parent> <old-parent-tip>.
        # A bare `git rebase <parent>` replays the parent's commits into the child.
        assert "--onto" in plan, plan
        rebases = [c for c in _commands(plan) if "rebase" in c and "--onto" not in c]
        bare = [c for c in rebases if not any(f in c for f in ("--continue", "--abort", "-i"))]
        assert not bare, f"bare rebase would duplicate the parent's commits: {bare}"

    def test_uses_a_recorded_sha_as_the_replay_boundary(self, plan: str):
        # --onto is only correct with the parent's *old* tip as the boundary, so
        # at least one recorded SHA has to appear in the commands.
        shas = ["e460113", "b66c6b0", "790a6a5", "3de0101"]
        assert any(s in plan for s in shas), f"no recorded tip used as a boundary:\n{plan}"

    def test_works_bottom_up(self, plan: str):
        order = [plan.find(b) for b in ("feat/restack-skill", "feat/forge-token")]
        assert -1 not in order, plan
        assert order[0] < order[1], "the bottom branch has to be rebased first"

    def test_force_push_is_leased(self, plan: str):
        pushes = [c for c in _commands(plan) if "push" in c]
        assert pushes, f"a restack that never pushes leaves the PRs stale:\n{plan}"
        for push in pushes:
            if "--force" in push:
                assert "--force-with-lease" in push, f"unleased force-push: {push}"

    def test_never_force_pushes_the_base_branch(self, plan: str):
        for push in (c for c in _commands(plan) if "push" in c and "force" in c):
            assert not re.search(r"\bmain\b", push), f"force-pushed the base branch: {push}"


@requires_eval_env
class TestMergedBottom:
    @pytest.fixture(scope="class")
    def plan(self) -> str:
        return run_skill("restack", MERGED_BOTTOM_CONTEXT, instruction=PLAN_INSTRUCTION)

    def test_drops_the_merged_commits_instead_of_replaying_them(self, plan: str):
        # --onto origin/main <merged-branch-old-tip> drops what already landed;
        # rebasing the child onto its dead parent resurrects the squashed commits.
        assert "--onto" in plan, plan
        assert "e460113" in plan, f"the merged branch's old tip is the boundary:\n{plan}"

    def test_does_not_rebase_onto_the_merged_branch(self, plan: str):
        for cmd in _commands(plan):
            if "rebase" in cmd and "--onto" in cmd:
                target = cmd.split("--onto", 1)[1].strip().split()[0]
                assert target != "feat/restack-skill", f"rebased onto a merged branch: {cmd}"


@requires_eval_env
class TestScopeRefusal:
    def test_a_lone_branch_is_not_a_stack(self):
        out = run_skill("restack", SINGLE_BRANCH_CONTEXT, instruction=PLAN_INSTRUCTION)
        # "When NOT to use": one branch off the base is a plain rebase. The tell
        # that the model over-applied the skill is --onto machinery on a chain
        # of one.
        assert "--onto" not in out, f"stack machinery applied to a single branch:\n{out}"


class TestTheAssertionsCanFail:
    """Guard the guard: a model eval that can't fail is decoration.

    Each check above is re-run here against a deliberately wrong plan, so a
    regression in the parsing can't quietly turn every eval green.
    """

    BAD_PLAN = """\
    git rebase feat/restack-skill feat/forge-token
    git push --force origin feat/forge-token
    git push --force origin main
    """

    def test_bare_rebase_is_detected(self):
        rebases = [c for c in _commands(self.BAD_PLAN) if "rebase" in c and "--onto" not in c]
        assert rebases, "the bare-rebase check would never fire"

    def test_unleased_force_push_is_detected(self):
        pushes = [c for c in _commands(self.BAD_PLAN) if "push" in c and "--force" in c]
        assert pushes and not any("--force-with-lease" in p for p in pushes)

    def test_base_branch_push_is_detected(self):
        pushes = [c for c in _commands(self.BAD_PLAN) if "push" in c and "force" in c]
        assert any(re.search(r"\bmain\b", p) for p in pushes)


class TestSpecReachesTheModel:
    """Runs without the eval env: the prompt is built locally, no model needed."""

    def test_no_literal_tokens_survive(self):
        body = load_skill_body("restack")
        assert "{{" not in body, "an unsubstituted token would reach the model as text"

    def test_forge_commands_are_present(self):
        # Phase 6 is forge-specific; without the adapter the model has no
        # retarget command to name.
        assert "gh pr edit" in load_skill_body("restack")

    def test_forge_choice_is_honored(self):
        body = load_skill_body("restack", forge="gitlab")
        assert "glab mr update" in body
        assert "gh pr edit" not in body
