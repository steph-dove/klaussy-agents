---
name: {{REPO}}-rest-of-the-owl
description: Use when the user hands you a task definition and wants the ENTIRE development loop run end-to-end — plan, implement, review and fix, QA the change with evidence appropriate to it, open a humanized PR, then poll CI and code review, fixing and resolving until the PR is green and clean. Does everything except merge. Long-running and autonomous; the human keeps the merge button.
allowed-tools: Read Grep Glob Bash Edit Write TodoWrite Agent
---

## Task

`$ARGUMENTS`

If `$ARGUMENTS` is empty, use the task definition the user pasted into the conversation (a ticket, a design note, a one-line ask). If there is none, stop and ask for one — this skill needs a target.

## The bit

*How to draw an owl: (1) draw two circles. (2) draw the rest of the owl.* The user just handed you the two circles — a task definition. This skill draws the rest of the owl: the whole lifecycle from "here's what I want" to "here's a green, reviewed PR waiting for your merge." It is a genuine end-to-end run, not a gag — but it earns the name by doing the enormous unglamorous middle the meme skips over.

**It does everything except merge.** The merge button stays with the human. Never merge, never force-push over someone else's work, never mark the PR ready-to-merge on the user's behalf.

## How this skill works

You orchestrate the repo's other skills as a pipeline. Each phase below names the sibling skill whose playbook you follow — open that skill's `SKILL.md` and run its steps, then come back here for the next phase. Track the whole run with TodoWrite: one todo per phase, `in_progress` when you start it, `completed` when it's done. The flow is long and mostly unattended; the todo list is how the user follows along.

Stop and hand back to the user (do not barrel ahead) if any phase hits something a human must decide: a missing secret or env var, an ambiguous requirement the task definition doesn't settle, a destructive migration, or a test failure that looks like a real bug in existing code rather than in your change.

## Phase 1 — Plan

Follow **`{{REPO}}-plan`** (or **`{{REPO}}-implement`**'s lighter planning phase for a small, single-surface task). Produce a concrete build sequence. If the task definition leaves a real ambiguity, ask now — a wrong assumption here costs the whole owl.

## Phase 2 — Implement

Follow **`{{REPO}}-implement`**. Work the plan in small batches, keeping the suite green as you go. For a bug fix, write the failing test first. Do not scope-creep beyond the task definition.

## Phase 3 — Local review and fix

Follow **`{{REPO}}-review`** against the working diff (`git diff {{BASE_BRANCH}}...HEAD`). Fix every finding you agree with; for ones you don't, note why. Re-run the suite. Then follow **`{{REPO}}-self-review`** as a last pass so the diff doesn't read as AI-written. Do not open the PR until this phase is clean.

## Phase 4 — QA the change

Follow **`{{REPO}}-qa`**. It classifies the diff and runs only the QA that fits: screenshots for a UI change, the exercised endpoint plus e2e for a backend change, command output for a CLI, tests for a library — and nothing at all for a docs/config-only change. Don't hand-pick the QA yourself; let the skill right-size it to what the diff touches. Keep the artifacts it saves under `.qa/` — Phase 5 folds them into the PR so the reviewer sees the change actually working.

## Phase 5 — Open the PR (humanized)

1. Commit the work on a topic branch (never commit straight to `{{BASE_BRANCH}}`) and push.
2. Draft the PR body from the task definition + what you actually built, using **`{{REPO}}-pr`**'s Summary / Changes / Test Plan structure. Fold in the Phase 4 QA summary — for a UI change, reference the screenshots (note that `gh pr create` can't upload images, so link the `.qa/` paths and prompt the user to drag them in, unless the repo has an image-hosting convention); for backend/CLI, paste the captured output.
3. Run the body through **`{{REPO}}-humanize`** before it goes out — the description is the most-read prose in the whole change; it must not read like a chatbot wrote it.
4. Open the PR with `gh pr create` (base `{{BASE_BRANCH}}`). Capture the PR number/URL and report it.

## Phase 6 — Re-review the PR and fix

Now that the diff is a real PR, review it once more with **`{{REPO}}-review`** (a PR at rest reads differently than an uncommitted diff — integration seams and the change as a whole surface here). Fix findings, commit, push.

## Phase 7 — Poll CI and fix failures

Watch the checks until they reach a terminal state:

```
gh pr checks <number> --watch
```

For each failing check, pull its logs (`gh run view <run-id> --log-failed`), diagnose the *real* cause, fix it, commit, push, and re-watch. A flaky check gets one re-run before you treat it as a genuine failure — don't loop forever re-running a green-on-retry check, and don't paper over a real failure by disabling the test. If a failure is in code your change didn't touch and can't have caused, stop and tell the user rather than guessing.

## Phase 8 — Poll for code review and resolve

Once CI is green, wait for review to land (human or bot). Poll on a sane cadence — check, wait, check — rather than hammering the API:

```
gh pr view <number> --json reviews,reviewDecision,comments
gh api repos/{owner}/{repo}/pulls/<number>/comments   # inline review threads
```

For the feedback that arrives, follow **`{{REPO}}-address-review`**: triage each comment, apply the changes it warrants, draft a reply, and resolve the thread once handled. Push fixes, which re-triggers CI — loop back to Phase 7 if anything goes red.

**Bounded wait.** Reviews depend on a human showing up, so do not poll indefinitely. If no new review activity arrives after a reasonable window (say, several polls over ~15 minutes, or immediately if the user tells you to wrap up), stop polling and hand back with a summary. Resume later when the user says review has landed.

## Phase 9 — Land the owl (but don't merge)

When CI is green and all review threads are resolved, stop. Report: the PR link, its check status, which review comments you addressed and how, and the one thing left — the user's merge. Mark all TodoWrite tasks complete.

State plainly if you stopped early and why (waiting on review, blocked on a decision, a failure you wouldn't paper over).

## Rules

- **Never merge, never mark ready-to-merge, never force-push over other commits.** The human owns the merge.
- **No scope creep across the whole owl.** The task definition is the contract. Fixing a review comment is in scope; rewriting an unrelated subsystem because you noticed it is not.
- **Don't fake green.** Never disable, skip, or `xfail` a test, loosen a lint rule, or `--no-verify` past a guard to make CI pass. A red check is information; fix the cause.
- **Humanize anything the user will read** — PR body, review replies, commit messages. Run **`{{REPO}}-humanize`** on prose before it ships.
- **Stop for humans on human decisions** — missing secrets, ambiguous requirements, destructive changes, or a failure that points at a pre-existing bug.

## When NOT to use

- The user wants just one phase — planning, or a review, or a PR description. Use that skill directly; the full owl is overkill.
- The task isn't defined well enough to build unattended. Nail the definition down first (or use **`{{REPO}}-plan`**, which forces the clarifying questions), then come back.
- The change must be merged, released, or deployed as part of the ask — this skill deliberately stops at the merge button. Do that step yourself, with a human in the loop.
