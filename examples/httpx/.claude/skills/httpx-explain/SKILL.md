---
name: httpx-explain
description: Use when the user wants code, a concept, or the current diff explained in this repo. With no specific target, explains the current branch diff; with a target, traces call chains and data flow end-to-end and explains in plain language.
allowed-tools: Read Grep Glob Bash(git diff *)
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, explain the current branch diff using the dump below. Otherwise, treat `$ARGUMENTS` as the target — a file path, function name, or concept — and explain that.

## Current branch diff (used when target is empty)

```!
git diff master...HEAD
```

## Instructions

**If the target is empty (no arguments):**
1. The diff above shows everything changed on this branch. If it's empty, fall back to `git diff` (unstaged) and `git diff --cached` (staged).
2. Read the full files involved to understand the surrounding context — do not paraphrase from the diff alone.
3. Explain what changed and why, covering:
   - The purpose of the changes as a whole
   - How the modified components interact
   - Any non-obvious behavior or edge cases introduced

**If the target is provided:**
1. Read CLAUDE.md and any matching `.claude/rules/*.md` for the area the target lives in.
2. Find the relevant code using Grep and Glob.
3. Read the full files involved to understand context.
4. Trace the call chain and data flow end-to-end.
5. Explain how it works in plain language, covering:
   - What it does and why it exists
   - Key components and how they interact
   - Important design decisions or trade-offs
   - Any non-obvious behavior or edge cases

## Rules

- Tailor the depth to the question — "what does this function do" needs less than "how does auth work".
- Use concrete examples from the code, not abstract descriptions.
- Cite file:line references when pointing at code.
- If something looks like a bug or smells off, mention it once, then stay focused on explaining.
- Don't suggest changes unless asked.

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

## When NOT to use

- The user wants to *change* code — use the implement, refactor, debug, or fix skill instead.
- The user wants a code review — use the review skill, which validates findings and structures output.
- The user wants the diff itself, not an explanation of it — they can run `git diff` directly.
