---
name: httpx-pr
description: Use when the user wants a PR description generated for the current branch. Reads commit history, file changes, and CLAUDE.md, then writes a Summary / Changes / Test Plan / Notes block to pr-description.md.
---

## Branch

Run `git branch --show-current` and use its output.

## Commit history vs base

Run `git log master..HEAD --oneline` and use its output.

## Files changed

Run `git diff master...HEAD --stat` and use its output.

## Instructions

Generate a PR description for the changes summarized above. Extract any ticket reference (e.g. FEAT-1234) from the branch name. Read CLAUDE.md for project conventions and any PR template rules. For key changed files, read them to understand the full context — do not paraphrase from the diff alone.

Output format:

```markdown
## Summary

<!-- 1-3 sentences explaining what this PR does and why -->

## Changes

<!-- Bullet list of key changes, grouped logically -->

## Test Plan

<!-- How the changes were tested -->
- [ ] Tests pass locally
- [ ] Manually verified

## Notes

<!-- Anything reviewers should pay attention to, migration steps, feature flags, etc. -->
```

Rules:
- **Write for a reviewer who has 30 seconds.** Lead with what changed and why it matters; surface the one thing they must look at. The Summary should orient them before they open a single file.
- **Don't echo the diff.** The reviewer can read the diff. Summarize intent and group related changes — do not narrate every edit line by line.
- **Describe the current end state, not a changelog.** Write what the PR *is*, not a chronological story of how you got there ("first I tried X, then changed to Y"). If you revised an approach mid-branch, describe only the final shape.
- Be specific — reference actual file names, functions, and components.
- Focus on the "why" not just the "what".
- If the branch name has a ticket reference, include it in the summary.
- Keep it concise. No filler.
- If there are database changes, call them out explicitly.
- If there are new dependencies, mention them.

### Write like a person, not a chatbot

Whatever you output for the user (comments, descriptions, messages) must read as if a human engineer wrote it. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

- **No em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite. This is the single biggest AI tell.
- **No filler openers.** Cut "It's worth noting that", "It's important to note that", "I noticed that", "I wanted to point out that", "Please note that", "Just to mention", "Worth noting", "Note that". State the point directly.
- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps", "Feel free to...", "Happy to help", "Let me know your thoughts".
- **Tighten hedges.** "in order to" → "to"; "could potentially" → "could"; "may potentially" → "may". Drop stacked qualifiers.
- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**
- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **Don't mirror the thread's tone.** When you reply to an existing comment, review note, or message, read it for substance but not for temperature: neutralize any rudeness or bluntness in it before you draft. Hostile or curt input must not prime a hostile or curt reply, answer as if the other person had phrased it civilly.
- **Be short, then cut more.** Lead with the point. Keep the decision and the one fact that justifies it, then stop. A reply in a thread is usually one sentence; a single review comment one to five. Don't pad to sound thorough or stack throat-clearing ahead of the point.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop detail the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact; drop what's merely supporting. This is the one place humanizing may drop content, never reverse or invent meaning, but you need not preserve every clause.
- Vary sentence shape; don't open every line the same way. Never reword code, identifiers, or anything inside backticks or fences. Humanize prose only.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Good call, done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: Good call. `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

Write the output to `pr-description.md` in the repo root.

## When NOT to use

- The user wants to actually open a PR (`gh pr create`) — this skill only writes the description text into a file.
- The branch has no commits ahead of `master` — there's nothing to describe; tell the user instead.
- The user wants a release-notes-style summary spanning multiple PRs — different shape; don't try to fit it in this template.
