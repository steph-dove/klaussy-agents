---
name: {{REPO}}-address-review
description: Use when a PR has review feedback and the user wants it addressed — pull the review comments, triage each one, apply the changes it warrants, and draft replies. Closes the loop between a review and the follow-up commit; it does not re-review the code from scratch.
allowed-tools: Read Grep Glob Bash Edit Write
---

Address the review feedback on the current PR. Every comment gets a response: a change, or a reasoned reply explaining why not. Don't silently skip any.

## Phase 1: Gather the feedback

1. **Get the review comments.** If `gh` is available, pull them for the current branch's PR: `gh pr view --json reviews,comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments` for inline (line-level) comments. If `gh` isn't available or there's no PR, ask the user to paste the feedback.
2. **Read CLAUDE.md** and any `.claude/rules/*.md` covering the touched files — a fix must still satisfy the repo's conventions.
3. **Build the change list.** For each comment, capture: the file/line, what's asked, and the reviewer's intent (not just the literal words). Group comments that touch the same code so you fix each spot once.

## Phase 2: Triage each comment

Sort every comment into one of:

- **Accept & fix** — a real issue or a clear improvement. Most comments.
- **Accept with a different fix** — the concern is valid but the reviewer's suggested change isn't the best one; do the better fix and say why in the reply.
- **Discuss / decline** — you believe the current code is correct, or the change is out of scope. This is legitimate, but it requires a specific, respectful reason, not a dismissal. When unsure whether to decline, ask the user rather than deciding unilaterally.

State the triage before editing, so the user can redirect if they disagree.

## Phase 3: Apply the changes

1. **Make each accepted change** as a minimal, targeted edit — fix what the comment raised, don't refactor around it.
2. **Check for siblings.** If a comment points at a pattern (not just one line), grep for the same pattern elsewhere in the diff and fix those too, unless the reviewer scoped it to the one spot.
3. **Re-verify after editing** — run the tests/lint from CLAUDE.md. A fix that breaks the suite isn't done.
4. **Keep the changes reviewable.** One logical follow-up; don't fold in unrelated work that a re-review would have to untangle.

## Phase 4: Reply and hand off

1. **Draft a reply per comment** (or per group): what you changed and where, or — for a decline — the specific reason. Keep each to a sentence or two.
2. **Summarize** the follow-up: which comments led to changes, which were declined and why, and the suggested commit message (`fix: address review feedback` or per the repo convention).
3. **Do not push, resolve threads, or re-request review** unless the user asks — leave those actions to them.

{{HUMANIZE}}

## Rules

- Respond to every comment — a change or a reason. Silence on a comment reads as ignoring the reviewer.
- Critique the code, never the reviewer; when you decline, give evidence, not a brush-off. Read a blunt comment for its substance, not its tone, and reply civilly regardless.
- Don't over-correct: fix what was raised, not the whole file. Scope creep in a review-response commit makes the re-review harder.
- If two comments conflict, or a comment contradicts CLAUDE.md, surface the conflict to the user instead of silently picking one.

## When NOT to use

- There's no review yet — the user wants their branch reviewed; use the review skill.
- The feedback is a full redesign, not line comments — that's a re-plan; use the plan skill.
- The user only wants the reply text drafted, not the code changed — draft the replies and skip the edit phase.
