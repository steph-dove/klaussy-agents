---
name: fastapi-rest-of-the-owl
description: Use when the user hands you a task definition and wants the ENTIRE development loop run end-to-end — plan, implement, review and fix, QA the change with evidence appropriate to it, open a humanized PR, then poll CI and code review, fixing and resolving until the PR is green and clean. Does everything except merge. Long-running and autonomous; the human keeps the merge button. Also known as `klaussy-rest-of-the-owl`.
---

> **Adapted for opencode.**
>
> - This skill orchestrates parallel sub-agents using Claude's `Agent` tool / `subagent_type` syntax. On opencode, use opencode's subagents: `@`-mention one (built-in `@general`, `@explore`, `@scout`, or a project-defined subagent) or let the primary agent invoke them automatically by their description. They run in parallel child sessions, so the fan-out is real — launch all the lenses/validators at once rather than applying them sequentially.

## Task

`$ARGUMENTS`

If `$ARGUMENTS` is empty, use the task definition the user pasted into the conversation (a ticket, a design note, a one-line ask). If there is none, stop and ask for one — this skill needs a target.

## The bit

*How to draw an owl: (1) draw two circles. (2) draw the rest of the owl.* The user just handed you the two circles. This skill draws the rest: the whole lifecycle from "here's what I want" to "here's a green, reviewed PR waiting for your merge", including the enormous unglamorous middle the meme skips.

**It does everything except merge.** The merge button stays with the human. Never merge, never force-push over someone else's work, never mark the PR ready-to-merge on the user's behalf.

## How this skill works

You are an orchestrator. Each phase below names the sibling skill that owns that work: open that skill's `SKILL.md`, follow it, come back here. This file holds the sequence and the gates between phases, not the steps — where a phase and its skill disagree, the skill wins on *how* and this file wins on *when to stop*.

Track the run with TodoWrite: one todo per phase, `in_progress` when you start it, `completed` when it's done. The flow is long and mostly unattended; the todo list is how the user follows along.

**Keep the main context lean.** Everything you read stays in this conversation and is re-read on every later turn, so hand the read-heavy phases (review, self-review, QA) to a sub-agent when your agent has one. Give it the skill to follow, the base branch, and the exact shape of what to return; it returns a short summary and you act on that. Two exceptions run inline: an agent with no sub-agents, and a review of 150 or more reviewable lines, which takes review's parallel path (a sub-agent can't start sub-agents of its own).

**Stop and hand back** — don't barrel ahead — whenever a phase hits something a human must decide: a missing secret or env var, an ambiguous requirement, a destructive migration, or a test failure that looks like a real bug in existing code rather than in your change.

## Pre-flight

1. **Permissions.** If routine dev permissions aren't configured for this worktree yet, run **`fastapi-grant-permissions`** so editing, tests, git and the forge CLI don't prompt all run.
2. **Base branch.** Decide once which branch this targets and use it as `<base>` everywhere. First that applies: one the task or user names; the target of an existing request for this branch; the remote default (`git symbolic-ref --short refs/remotes/origin/HEAD` minus `origin/`); `master`. If the branch was cut from another topic branch instead, ask rather than guess — a wrong base puts someone else's commits in your diff. Say which you picked in the first progress update.

## Phases

| # | Follow | Gate before moving on |
| :-- | :--- | :--- |
| 1 | **`fastapi-plan`** (or **`fastapi-implement`**'s lighter planning for a small, single-surface task) | An approved `plan.md`. Ask now if the task leaves a real ambiguity; a wrong assumption costs the whole owl. Keep the plan and any breaking-change notes as session notes per **`fastapi-session-context`**. |
| 2 | **`fastapi-implement`** | The plan's boxes are ticked and the suite is green. No scope creep beyond the task definition. |
| 3 | **`fastapi-review`** against `git diff <base>...HEAD`, then **`fastapi-self-review`** | Every finding you agree with is fixed, the rest noted with a reason, suite re-run. Sub-agent returns the verdict line and one line per finding (severity, `file:line`, fix). |
| 4 | **`fastapi-qa`** | QA is genuinely clean. Let the skill right-size the evidence; don't hand-pick it. Sub-agent returns each check with pass/fail, the artifacts folder, and any asset URLs for the PR body. |
| 5 | **`fastapi-pr`** | The request is open against `<base>`, its number and URL reported. Commit on a topic branch (never straight to `<base>`) and push first. Embed the QA evidence from Phase 4 in the body. |
| 6 | **`fastapi-review`** again, now that it's a real PR | Findings fixed, committed, pushed. A PR at rest reads differently: integration seams and the change as a whole surface here. |
| 7 | `waiting.md`, then the adapter's CI commands | Every check is green. |
| 8 | `waiting.md`, then **`fastapi-address-review`** | Every comment answered and its thread resolved. Pushing fixes re-triggers CI, so go back to 7 if anything goes red. |
| 9 | — | Stop. Report and hand back. |

**Phase 4 is a gate, not a formality.** If QA shows the change is broken or ugly, go back to phase 2 or 3, fix it, and re-QA. Don't open a PR on a change QA has already failed and leave it for CI or the reviewer to catch.

**Phase 7: fixing CI.** Pull each failing check's logs with the adapter's log command and fix the real cause. A flaky check gets one re-run before you treat it as genuine. If a failure is in code your change didn't touch and can't have caused, stop and tell the user rather than guessing.

**Phase 9: landing.** Report the PR link, its check status, which review comments you addressed and how, the QA artifacts folder and anything still to attach by hand, and the one thing left: the user's merge. Mark all TodoWrite tasks complete. Say plainly if you stopped early and why.

### Forge commands (GitHub)

`origin` points at GitHub, so the `gh` CLI is the adapter. Confirm a flag with `gh <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `gh issue view <n> --comments` |
| Open a request | `gh pr create --base <branch> --title <title> --body-file <file>` |
| Request status | `gh pr view <n> --json state,mergeable,reviewDecision,baseRefName` |
| CI status | `gh pr checks <n>`, then `gh run view <run-id> --log-failed` on a failure |
| Retarget a request | `gh pr edit <n> --base <branch>` |

`{owner}/{repo}` are placeholders `gh` fills from the current repo, leave them literal.

## Rules

- **Never merge, never mark ready-to-merge, never force-push over other commits.** The human owns the merge.
- **No scope creep across the whole owl.** The task definition is the contract. Fixing a review comment is in scope; rewriting an unrelated subsystem because you noticed it is not.
- **Don't fake green.** Never disable, skip or `xfail` a test, loosen a lint rule, or `--no-verify` past a guard to make CI pass. A red check is information; fix the cause.
- **Stop for humans on human decisions** — missing secrets, ambiguous requirements, destructive changes, or a failure that points at a pre-existing bug.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

## When NOT to use

- The user wants just one phase — planning, or a review, or a PR description. Use that skill directly; the full owl is overkill.
- The task isn't defined well enough to build unattended. Nail the definition down first (or use **`fastapi-plan`**, which forces the clarifying questions), then come back.
- The change must be merged, released, or deployed as part of the ask — this skill deliberately stops at the merge button. Do that step yourself, with a human in the loop.
