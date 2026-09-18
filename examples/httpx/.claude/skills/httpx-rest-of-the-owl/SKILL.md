---
name: httpx-rest-of-the-owl
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

## Pre-flight — Permissions

If routine dev permissions are not yet configured for this worktree, invoke **`httpx-grant-permissions`** first so file editing, test execution, git operations, and forge CLI commands run unprompted throughout the loop.

## Phase 1 — Plan

Follow **`httpx-plan`** (or **`httpx-implement`**'s lighter planning phase for a small, single-surface task). Produce a concrete build sequence. Save the approved plan as an uncommitted OKF session note in `$KLAUSSY_SESSION_NOTES_DIR/<agent-name>-plan.md` (or `%KLAUSSY_SESSION_NOTES_DIR%\<agent-name>-plan.md` on Windows, or `plan.md` at worktree root) following the Open Knowledge Format protocol (YAML frontmatter with `type: session-note`, `tags: [plan, design, devloop]`, `generated: { by: <provider-id>/<agent-name>, at: <ISO-8601 timestamp> }`). If the task definition leaves a real ambiguity, ask now — a wrong assumption here costs the whole owl.

## Phase 2 — Implement

Follow **`httpx-implement`**. Work the plan in small batches, keeping the suite green as you go. For a bug fix, write the failing test first. Record any breaking changes or shared context notes in `$KLAUSSY_SESSION_NOTES_DIR/` (or `%KLAUSSY_SESSION_NOTES_DIR%` on Windows). Do not scope-creep beyond the task definition.

## Phase 3 — Local review and fix

Follow **`httpx-review`** against the working diff (`git diff master...HEAD`). Fix every finding you agree with; for ones you don't, note why. Re-run the suite. Then follow **`httpx-self-review`** as a last pass so the diff doesn't read as AI-written. Do not open the PR until this phase is clean.

## Phase 4 — QA the change

Follow **`httpx-qa`**. It classifies the diff and runs only the QA that fits:
- **UI / Frontend changes**:
  - Capture **before and after screenshots** for visual comparison, formatted in a comparison table.
  - Record a **full-flow video (.mp4)** demonstrating the complete interaction end-to-end. The video MUST showcase responsive UI behaviors by resizing (growing and shrinking) the window or viewport.
  - Save all media in `Downloads/klaussy-qa-<branch>/` (`~/Downloads/klaussy-qa-<branch>/` on macOS/Linux, `%USERPROFILE%\Downloads\klaussy-qa-<branch>\` on Windows).
  - Programmatically upload QA media assets (e.g. using `gh release upload`, `gh api` assets endpoint, or image host) so you have direct asset URLs ready to attach to the PR description.
- **Backend / CLI changes**:
  - Exercise endpoints, run integration suites, and capture execution output.

Don't hand-pick the QA yourself; let the skill right-size it to what the diff touches.

**QA is a gate, not a formality — clear it before you touch the PR.** The whole point of running QA here is to catch problems *before* they become CI failures or reviewer comments. If QA surfaces anything wrong — a screenshot that shows the change is broken or ugly, an endpoint returning the wrong response, a CLI erroring, a failing test — stop and fix it: loop back to Phase 2/3, correct the change, and re-QA. Do NOT open the PR (Phase 5) on a change that QA has shown to be broken and then rely on CI or the reviewer to catch it. Only advance once QA is genuinely clean (or the only gaps are ones you've explicitly flagged as un-QA-able and told the user about).

## Phase 5 — Open the PR (humanized)

1. Commit the work on a topic branch (never commit straight to `master`) and push.
2. Draft the PR body from the task definition + what you actually built, using **`httpx-pr`**'s Summary / Changes / Test Plan structure. For UI changes, embed the Before/After comparison table and uploaded video links into the PR description; for backend/CLI, paste the captured output.
3. Run the body through **`httpx-humanize`** before it goes out — the description is the most-read prose in the whole change; it must not read like a chatbot wrote it.
4. Open the request against `master` with the adapter's create command. Capture its number/URL and report it.

### Forge commands (GitHub)

`origin` points at GitHub, so the `gh` CLI is the adapter. Confirm a flag with `gh <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `gh issue view <n> --comments` |
| Open a request | `gh pr create --base <branch> --title <title> --body-file <file>` |
| Request status | `gh pr view <n> --json state,mergeable,reviewDecision,baseRefName` |
| CI status | `gh pr checks <n>`, then `gh run view <run-id> --log-failed` on a failure |
| Read review comments | `gh api repos/{owner}/{repo}/pulls/<n>/comments` |
| Reply in a thread | `gh api --method POST repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body=<text>` |
| Resolve a thread | two steps, see below — REST can't do it |
| Retarget a request | `gh pr edit <n> --base <branch>` |

`{owner}/{repo}` are placeholders `gh` fills from the current repo, leave them literal.

**Resolving needs GraphQL, and the id it wants is not the comment id.** The REST comment objects don't carry it, so read the thread ids first, then resolve one:

```
gh api graphql -f query='{ repository(owner: "<owner>", name: "<repo>") {
  pullRequest(number: <n>) { reviewThreads(first: 50) { nodes {
    id isResolved comments(first: 1) { nodes { databaseId body } } } } } } }'

gh api graphql -f query='mutation($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }' -F id=<thread-node-id>
```

Match a thread to the comment you replied to through `comments.nodes[].databaseId`, which is the REST comment id. `threadId` is the only required input.

A reply must name the thread it answers. The `replies` endpoint above takes only `body`; the alternative is `POST .../pulls/<n>/comments` with `-F in_reply_to=<comment-id>` (an integer, hence `-F`). Posting to `comments` without `in_reply_to` opens a new top-level review comment rather than replying.

**GitHub has native stacks**, driven by the `gh-stack` extension. `gh extension list` says whether it's installed. If it isn't, **offer to install it** — `gh extension install github/gh-stack`, one command, no repo changes — and say what it buys before asking: a stack map and layer navigation on every request page, plus cascading rebase when the base moves. Ask rather than installing unprompted, since it touches the user's `gh` setup and not this repo, but do ask; silently settling for bare chained bases hands back a worse result than the one command would have. Declining is a fine answer and the fallback below still works.

The extension is in public preview, so check `gh stack <command> --help` before relying on a flag.

| Need | Command |
| :--- | :--- |
| Link requests that already exist into a stack | `gh stack link --base <branch> <branch-or-pr> <branch-or-pr> ...` |
| Track a carved chain locally | `gh stack init --base <branch> <branch> ...` |
| Push the tracked chain and open or update its requests | `gh stack submit` |
| See the stack | `gh stack view` |
| Cascading rebase after the base moved | `gh stack rebase` |
| Fetch, rebase, push, and sync in one pass | `gh stack sync` |

Arguments run bottom-up, nearest the base first. Two constraints decide whether a stack is available at all: **every branch must live in this repo** (cross-fork stacks aren't supported), and the extension has to be installed.

`link` and `init` are two different entry points and the difference shows up later. `link` stacks requests that already exist and leaves nothing behind locally, so a later `gh stack rebase` needs `gh stack checkout <stack-number>` first to pick the stack back up. `init` registers the branches locally up front and `submit` then opens the requests itself, which means the bodies are its own — write them with `gh pr edit <n> --body-file` afterwards if they have to say something specific.

Without it, chained `--base` targets still give reviewers a per-layer diff, and GitHub often offers to convert an eligible chain into a stack — a banner on the request, or "Add to stack" behind the stack icon. Say which route you took.


## Phase 6 — Re-review the PR and fix

Now that the diff is a real PR, review it once more with **`httpx-review`** (a PR at rest reads differently than an uncommitted diff — integration seams and the change as a whole surface here). Fix findings, commit, push.

## Phase 7 — Poll CI and fix failures

Watch the checks until they reach a terminal state, using the adapter's CI status command (poll on a sane cadence if it has no watch mode).

For each failing check, pull its logs with the adapter's log command, diagnose the *real* cause, fix it, commit, push, and re-watch. A flaky check gets one re-run before you treat it as a genuine failure — don't loop forever re-running a green-on-retry check, and don't paper over a real failure by disabling the test. If a failure is in code your change didn't touch and can't have caused, stop and tell the user rather than guessing.

## Phase 8 — Poll for code review and resolve

Once CI is green, wait for review to land (human or bot). Poll on a sane cadence — check, wait, check — rather than hammering the API, using the adapter's status and review-comment commands. Inline comments and the summary review body come from different endpoints on every provider, so read both.

For the feedback that arrives, follow **`httpx-address-review`**: triage each comment, apply the changes it warrants, draft a reply, and resolve the thread once handled. Push fixes, which re-triggers CI — loop back to Phase 7 if anything goes red.

**Bounded wait.** Reviews depend on a human showing up, so do not poll indefinitely. If no new review activity arrives after a reasonable window (say, several polls over ~15 minutes, or immediately if the user tells you to wrap up), stop polling and hand back with a summary. Resume later when the user says review has landed.

## Phase 9 — Land the owl (but don't merge)

When CI is green and all review threads are resolved, stop. Report: the PR link, its check status, which review comments you addressed and how, the path to the QA artifacts folder and which recordings still need dragging into the PR, and the one thing left — the user's merge. Mark all TodoWrite tasks complete.

State plainly if you stopped early and why (waiting on review, blocked on a decision, a failure you wouldn't paper over).

## Rules

- **Never merge, never mark ready-to-merge, never force-push over other commits.** The human owns the merge.
- **No scope creep across the whole owl.** The task definition is the contract. Fixing a review comment is in scope; rewriting an unrelated subsystem because you noticed it is not.
- **Don't fake green.** Never disable, skip, or `xfail` a test, loosen a lint rule, or `--no-verify` past a guard to make CI pass. A red check is information; fix the cause.
- **Humanize anything the user will read** — PR body, review replies, commit messages. Run **`httpx-humanize`** on prose before it ships.
- **Stop for humans on human decisions** — missing secrets, ambiguous requirements, destructive changes, or a failure that points at a pre-existing bug.

## When NOT to use

- The user wants just one phase — planning, or a review, or a PR description. Use that skill directly; the full owl is overkill.
- The task isn't defined well enough to build unattended. Nail the definition down first (or use **`httpx-plan`**, which forces the clarifying questions), then come back.
- The change must be merged, released, or deployed as part of the ask — this skill deliberately stops at the merge button. Do that step yourself, with a human in the loop.
