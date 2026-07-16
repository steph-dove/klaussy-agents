---
name: httpx-address-review
description: Use when a PR has review feedback and the user wants it addressed — pull the review comments, triage each one, apply the changes it warrants, and draft replies. Closes the loop between a review and the follow-up commit; it does not re-review the code from scratch.
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

### Write like a person, not a chatbot

Whatever you output for the user (comments, descriptions, messages) must read as if a human engineer wrote it. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

- **No em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite. This is the single biggest AI tell.
- **No filler openers.** Cut "It's worth noting that", "It's important to note that", "I noticed that", "I wanted to point out that", "Please note that", "Just to mention", "Worth noting", "Note that". State the point directly.
- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps", "Feel free to...", "Happy to help", "Let me know your thoughts".
- **Tighten hedges.** "in order to" → "to"; "could potentially" → "could"; "may potentially" → "may". Drop stacked qualifiers.
- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**
- **No excessive apologies.** Avoid apologetic filler ("Sorry about that!", "My apologies for the confusion", "Apologies for the oversight"). State the correction or resolution directly.
- **Prefer active, imperative verbs and avoid narration.** Use direct instructions (e.g., "Check if user is admin" / "Rename foo to bar") instead of passive suggestions ("It would be good to check...", "You might want to rename..."). Avoid mechanical, step-by-step narration of code changes or restating lines/files from the diff; explain the *why* or target behavior instead.
- **Avoid the LLM lexicon & buzzwords.** Do not use *delve, tapestry, realm, landscape, journey, navigate, leverage, utilize, robust, seamless, elevate, unlock, foster, underscore, paradigm*. Replace corporate jargon (e.g. leverage/utilize) with simpler words (e.g. use).
- **Avoid transition crutches.** Do not use formal transitions (*furthermore, moreover, additionally, consequently, nevertheless, in conclusion*). Use simpler ones or prune them entirely.
- **Avoid rhetorical reframes and standalones.** Avoid the negation-reframe ("not only... but also", "this isn't just a bug fix — it's...") and standalone summary lines ("And that's the whole point.").
- **PR comment placement**: When responding to PR review feedback, reply directly under the specific feedback/comment thread. Do not post replies in a separate/new top-level comment.
- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **No superlatives or ranking praise.** Don't editorialize a point's importance: cut "this is the sharpest catch in the review", "best catch", "great find", "excellent point", "the most important issue here". Rating a comment against the others is an AI tell and adds nothing. State the substance and stop.
- **Don't mirror the thread's tone.** When you reply to an existing comment, review note, or message, read it for substance but not for temperature: neutralize any rudeness or bluntness in it before you draft. Hostile or curt input must not prime a hostile or curt reply, answer as if the other person had phrased it civilly.
- **Don't thank a bot.** When the reviewer is an automated tool or bot (a review bot, another agent, a CI check), respond to the substance without gratitude or pleasantries aimed at it, no "thanks for the review", "good catch", or addressing it as a person. Reserve those for a human reviewer, and even then keep them minimal.
- **Be short, then cut more.** Lead with the point. Keep the decision and the one fact that justifies it, then stop. A reply in a thread is usually one sentence; a single review comment one to five. Don't pad to sound thorough or stack throat-clearing ahead of the point.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop detail the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact; drop what's merely supporting. This is the one place humanizing may drop content, never reverse or invent meaning, but you need not preserve every clause.
- Vary sentence shape; don't open every line the same way. Never reword code, identifiers, or anything inside backticks or fences. Humanize prose only.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Good call, done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: Good call. `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

## Rules

- Respond to every comment — a change or a reason. Silence on a comment reads as ignoring the reviewer.
- Critique the code, never the reviewer; when you decline, give evidence, not a brush-off. Read a blunt comment for its substance, not its tone, and reply civilly regardless.
- Don't over-correct: fix what was raised, not the whole file. Scope creep in a review-response commit makes the re-review harder.
- If two comments conflict, or a comment contradicts CLAUDE.md, surface the conflict to the user instead of silently picking one.

## When NOT to use

- There's no review yet — the user wants their branch reviewed; use the review skill.
- The feedback is a full redesign, not line comments — that's a re-plan; use the plan skill.
- The user only wants the reply text drafted, not the code changed — draft the replies and skip the edit phase.
