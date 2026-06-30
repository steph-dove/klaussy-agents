---
name: fastapi-humanize
description: Use when the user wants prose, comments, docs, or a file's text to read like a human engineer wrote it instead of an AI. Strips AI tells (em-dashes, filler openers, chatbot scaffolding) by rewriting, then runs klaussy's deterministic scrubber as a guaranteed backstop. Never touches code.
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, humanize the prose the user pasted into the conversation. Otherwise treat `$ARGUMENTS` as one or more file paths (or a glob) and humanize the prose in those files in place.

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

## Steps

1. **Get the prose.** For file targets, Read each file. For pasted text, work with what's in the conversation. If the text is a reply inside a thread (a review comment, a message chain), the surrounding comments are read-only context: take their substance, neutralize their tone in your head, and humanize only your own message. Don't carry the thread's bluntness or rudeness into what you write — see "Don't mirror the thread's tone" above.
2. **Rewrite by the rules above.** This is the judgment pass: kill filler openers, drop chatbot scaffolding, replace em/en dashes, tighten hedges, vary sentence shape. Only touch prose, never code, identifiers, or anything inside backticks or fences.
3. **Run the deterministic backstop.** klaussy ships a code-preserving scrubber that guarantees the high-confidence tells are gone regardless of the rewrite. This is the post-processing step, always run it last:
   - **Files:** `klaussy humanize <file>... --write` (rewrites in place; prints which files changed).
   - **Pasted text:** pipe the rewritten text through it, e.g. `printf '%s' "$text" | klaussy humanize`, and use that output.
   - If the `klaussy` CLI isn't on PATH, run it via `python -m klaussy humanize ...`. If neither resolves, say the deterministic backstop was unavailable and that only the rewrite was applied.
4. **Report** what changed: for files, the list the scrubber reported; for text, show the humanized result.

## Rules

- The deterministic scrubber is a conservative subset (dashes, a fixed set of openers/scaffolding, a few hedges). Your rewrite does the broader work the scrubber can't; the scrubber then guarantees the conservative tells. Run both, not just one.
- Preserve the decision and its rationale; never reverse, add, or invent meaning. Humanizing is mostly a tone/style edit, but brevity may drop low-value detail (explanatory parentheticals, restated identifiers, narration the diff already shows). Keep the load-bearing facts, cut what the reader can reconstruct (see "Cut detail, not just words" above).
- Never reword code, identifiers, fenced ```blocks```, or `inline code`. The scrubber already skips them; you must too.
- Don't "improve" prose beyond removing AI tells, keeping it civil (see "Don't let trimming tip into terse" above), and tightening length (see "Be short, then cut more") unless the user asks. Match the surrounding voice — a slightly blunt author stays slightly blunt, you only stop the trim from making them ruder.
- Shortest form that carries the decision. A reply in a thread should aim for one sentence; a single review comment one to five. If it runs long, cut detail the reader doesn't need, don't just compress what you said into denser prose.
- Use `klaussy humanize <file> --check` (exit 1 if anything would change, no writes) when the user only wants to know whether a file reads as AI-written.

## When NOT to use

- The user wants code changed, refactored, or fixed — use the implement, refactor, or fix skill.
- The user wants a review of the writing's substance, not its tells — that's a different request.
- The text is already plain and human; running the scrubber will report no changes, which is a valid outcome.
