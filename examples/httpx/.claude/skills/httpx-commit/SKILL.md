---
name: httpx-commit
description: Use when the user wants a commit message written for currently staged changes. Reads `git diff --cached`, recent log style, and CLAUDE.md, then outputs a conventional-commit-style message — type(scope) summary + why-focused body.
allowed-tools: Read Bash(git diff *) Bash(git log *) Bash(git branch *)
disable-model-invocation: true
---

## Staged changes

```!
git diff --cached --stat
```

```!
git diff --cached
```

## Recent commit style

```!
git log --oneline -10
```

## Current branch

```!
git branch --show-current
```

## Instructions

Write a commit message for the changes shown above. Read CLAUDE.md for any project-specific commit conventions before writing.

Format:

```
<type>(<scope>): <short summary>

<body — explain what changed and why, not how>
```

Types: feat, fix, refactor, test, docs, chore, style, perf
Scope: the area of code affected (e.g. auth, api, ui)

Rules:
- Summary line under 72 characters.
- Body wraps at 80 characters.
- Match the style of the recent commits shown above.
- Focus on "why" in the body, not "what" (the diff already shows "what").
- If the branch name has a ticket reference (e.g. FEAT-1234), include it in the body.

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

Output ONLY the commit message, nothing else. Do not wrap it in code blocks.

## When NOT to use

- The user wants to actually run `git commit` — this skill only writes the message text.
- Nothing is staged — ask the user to stage changes first instead of inventing a message.
- The user wants a commit message for unstaged or unmerged changes — point them at `git add` first.
