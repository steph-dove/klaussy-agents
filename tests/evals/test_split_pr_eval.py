"""Opt-in evals for the split-pr skill.

Splitting restructures work into new branches, so what's pinned here decides
whether the original survives and whether the result is reviewable: a backup
before the first carve, layers branched off each other rather than all off the
base, requests targeting the layer below, and a proof that the top of the stack
reproduces what you started with.

The negative case matters as much: a skill that splits everything handed to it is
worse than no skill, so a large-but-uniform diff has to come back as "don't".

See `harness.py` for what a prompt eval does and doesn't cover.
"""

from __future__ import annotations

import re

import pytest
from harness import load_skill_body, requires_eval_env, run_skill

# A diff with real seams: schema under API under UI, plus a rename sweep that
# wants to be its own layer.
LAYERED_CONTEXT = """\
`git status --porcelain` is empty. The branch `feat/team-invites` has 11 commits
ahead of main. The comment pass has already run and committed. `klaussy
split-prep --base main` reports 940 changed line(s), 902 code line(s), and
proposes these layers from the import graph:

  Layer 1  db/models.py, migrations/0042_invites.py
  Layer 2  services/mailer.py, api/serializers.py
  Layer 3  api/routes/invites.py
  Layer 4  web/components/InviteForm.tsx
  Layer 5  web/components/TeamPage.tsx
  Ungraphed: none

The files it graphed are:

  db/models.py                  +64   Invite model, status enum
  migrations/0042_invites.py    +38   new table
  api/routes/invites.py        +180   POST/GET/DELETE handlers
  api/serializers.py            +52   invite payloads
  services/mailer.py            +90   sends the invite email
  web/components/InviteForm.tsx +210  the form
  web/components/TeamPage.tsx   +74   renders the form
  tests/test_invites_api.py    +120   handler tests
  tests/test_mailer.py          +52   mailer tests
  (+ 29 files, +60 total)       renamed `Membership` -> `TeamMembership`
                                across the codebase, call sites only

The 11 commits are interleaved: most touch both `api/` and `web/`, and the
rename is spread across four of them. The user wants this split.
"""

# Large, but one mechanical pattern repeated. The right answer is "don't".
UNIFORM_CONTEXT = """\
`git status --porcelain` is empty. The branch `chore/py311-typing` has 3 commits
ahead of main and `klaussy review-prep --base main` reports 1,340 changed
line(s) across 78 files.

Every hunk is the same codemod: `Optional[X]` -> `X | None` and
`Dict[str, Y]` -> `dict[str, Y]`, applied by a script. No logic changed, no
signatures changed beyond the annotation text, and the suite passes untouched.
The user asks whether this should be split into stacked PRs.
"""

# Raw size says split; code size says don't. The comment pass is the difference.
COMMENT_INFLATED_CONTEXT = """\
`git status --porcelain` is empty. The branch `feat/report-export` has 4 commits
ahead of main. Nothing has been stripped or measured yet — you are at the start
of the run.

`git diff main...HEAD --stat` totals 1,180 changed lines across 9 files. Reading
the diff, most added hunks are long narration blocks: `export.py` alone adds a
14-line module docstring, a 9-line block explaining what a for-loop does, and a
comment above every assignment. The actual logic is one exporter class and two
helpers.
"""

# Nothing committed — the work is sitting in the working tree.
UNCOMMITTED_CONTEXT = """\
`git status --porcelain` shows 24 modified files and 6 untracked ones.
`git rev-list --count origin/main..HEAD` prints 0 — nothing has been committed;
the branch is level with main and all the work is in the working tree.
`git diff --stat` totals 810 changed lines spanning `db/`, `api/`, and `web/`.
The user wants this split into stacked PRs.
"""

PLAN_INSTRUCTION = (
    "Produce the exact git and gh commands you would run, in order, with a "
    "one-line reason for each. Do not run anything."
)


def _commands(text: str) -> list[str]:
    """Every git/gh command mentioned in the answer, prose or fenced."""
    return [m.group(0) for m in re.finditer(r"\b(?:git|gh)\s+[^\n`]+", text)]


@requires_eval_env
class TestLayeredSplitPlan:
    @pytest.fixture(scope="class")
    def plan(self) -> str:
        # The longest fixture against the longest spec: eight phases, and the
        # answer is a full command plan. It outruns the harness default.
        return run_skill("split-pr", LAYERED_CONTEXT, instruction=PLAN_INSTRUCTION, timeout=600)

    def test_backs_up_before_carving(self, plan: str):
        # The only complete undo. Without it a mis-carve three layers deep is
        # unrecoverable, since the original branch ref gets reused.
        branch_cmds = [c for c in _commands(plan) if re.search(r"\bgit branch\b", c)]
        assert branch_cmds, f"nothing backs up the original work:\n{plan}"
        assert any("prestack" in c for c in branch_cmds), (
            f"no -prestack backup branch before the carve: {branch_cmds}"
        )

    def test_layers_stack_on_each_other(self, plan: str):
        # The failure mode is carving every layer off main, which produces
        # overlapping PRs rather than a stack.
        checkouts = [c for c in _commands(plan) if "checkout -b" in c]
        assert len(checkouts) >= 2, f"fewer than two layers created:\n{plan}"
        off_base = [c for c in checkouts if re.search(r"\b(origin/)?main\b", c)]
        assert len(off_base) <= 1, (
            f"every layer branched off the base instead of the one below: {off_base}"
        )

    def test_verifies_the_stack_reproduces_the_original(self, plan: str):
        # `git diff <backup> <top-layer>` printing nothing is the check that a
        # hunk wasn't dropped on the floor during the carve.
        diffs = [c for c in _commands(plan) if re.search(r"\bgit diff\b", c)]
        assert any("prestack" in c for c in diffs), (
            f"the stack is never diffed against the backup:\n{plan}"
        )

    def test_requests_target_the_layer_below(self, plan: str):
        creates = [c for c in _commands(plan) if "pr create" in c]
        assert creates, f"a split that never opens the stack:\n{plan}"
        assert any("--base" in c for c in creates), f"no explicit base: {creates}"
        non_base = [c for c in creates if not re.search(r"--base\s+(origin/)?main\b", c)]
        assert non_base, f"every request targets main, so the stack has no layers: {creates}"

    def test_separates_the_mechanical_rename(self, plan: str):
        # The rename sweep touching 29 call-site files is the highest-value cut
        # available; folding it into a logic layer buries the logic.
        assert re.search(r"rename|membership", plan, re.I), (
            f"the rename sweep isn't called out as its own layer:\n{plan}"
        )

    def test_confirms_before_creating_branches(self, plan: str):
        assert re.search(r"confirm|approv|before .*creat|wait", plan, re.I), (
            f"no approval gate before the seams are committed to:\n{plan}"
        )


@requires_eval_env
class TestUniformDiffIsNotSplit:
    @pytest.fixture(scope="class")
    def answer(self) -> str:
        return run_skill("split-pr", UNIFORM_CONTEXT, instruction=PLAN_INSTRUCTION)

    def test_declines_to_split(self, answer: str):
        # 1,340 lines is well past any threshold, but it's one codemod. Splitting
        # by size alone is the thing this skill most needs to not do.
        assert re.search(
            r"(don'?t|do not|not worth|no need|shouldn'?t|keep it (as )?one|single (PR|request))",
            answer,
            re.I,
        ), f"split a uniform codemod on size alone:\n{answer}"

    def test_creates_no_branches(self, answer: str):
        carves = [c for c in _commands(answer) if "checkout -b" in c or "cherry-pick" in c]
        assert not carves, f"started carving a diff it should have left alone: {carves}"


@requires_eval_env
class TestCommentPassRunsFirst:
    @pytest.fixture(scope="class")
    def plan(self) -> str:
        return run_skill("split-pr", COMMENT_INFLATED_CONTEXT, instruction=PLAN_INSTRUCTION)

    def test_backs_up_before_editing_comments(self, plan: str):
        # The comment pass edits source, so it needs the same undo the carve has.
        # Order matters: a backup taken after the edit doesn't back the edit up.
        assert "prestack" in plan, f"no backup before a pass that rewrites files:\n{plan}"
        backup = plan.find("prestack")
        commit = plan.lower().find("tighten comment")
        if commit != -1:
            assert backup < commit, "backed up after editing comments, not before"

    def test_strips_comments_before_measuring(self, plan: str):
        assert re.search(r"comment", plan, re.I), f"never mentions the comment pass:\n{plan}"
        strip = plan.lower().find("comment")
        measure = plan.find("split-prep")
        if measure != -1:
            assert strip < measure, "measured before stripping — the size will be inflated"

    def test_sizes_on_code_lines_not_raw_lines(self, plan: str):
        assert re.search(r"code line|after (the )?(comment|cleanup)|split-prep", plan, re.I), (
            f"decided on the raw 1,180 figure without discounting comments:\n{plan}"
        )

    def test_the_cleanup_is_its_own_commit(self, plan: str):
        commits = [c for c in _commands(plan) if "commit" in c]
        assert commits, f"the comment pass is never committed:\n{plan}"


@requires_eval_env
class TestUncommittedWork:
    @pytest.fixture(scope="class")
    def plan(self) -> str:
        return run_skill("split-pr", UNCOMMITTED_CONTEXT, instruction=PLAN_INSTRUCTION)

    def test_normalizes_to_a_reference_commit(self, plan: str):
        # Carving straight from a dirty tree loses work on the first checkout;
        # the spec says snapshot it into one commit first.
        assert re.search(r"git (add|commit|stash)", plan), (
            f"carves from a dirty working tree without snapshotting it:\n{plan}"
        )

    def test_still_backs_up(self, plan: str):
        assert "prestack" in plan, f"no backup for uncommitted work:\n{plan}"


class TestSpecShape:
    """Cheap assertions on the shipped spec — no model, so these always run."""

    @pytest.fixture(scope="class")
    def body(self) -> str:
        return load_skill_body("split-pr")

    def test_substitutes_every_token(self, body: str):
        assert "{{" not in body, "an unsubstituted token would reach the model as text"

    def test_ships_the_forge_adapter(self, body: str):
        assert "gh pr create" in body, "no forge commands to open the stack with"

    def test_defers_to_the_shared_comment_rules(self, body: str):
        # The strip is destructive, and the guardrails that keep it off string
        # literals live in comment-cleanup.md. The spec must send the agent there
        # rather than restate them and drift.
        assert "comment-cleanup.md" in body, "no pointer to the canonical comment rules"

    def test_calls_the_layer_proposer(self, body: str):
        assert "split-prep" in body, "the import graph is never consulted"

    def test_points_at_restack_for_repair(self, body: str):
        # Creating a stack and repairing one are different jobs; the spec has to
        # hand off rather than grow its own rebase logic.
        assert "restack" in body, "no handoff to the skill that rebases the stack"
