---
name: httpx-document
description: Use when the user wants documentation written or updated — docstrings, API docs, a README section, or a doc comment on a tricky piece of code. Documents selectively: what a reader genuinely can't infer from the code, and nothing they can. Writes prose, not code changes.
---

Add documentation where it earns its place, and only there. The hard part of this skill is restraint: most code does not need a comment, and a docstring that restates the signature is worse than none — it rots, and it trains readers to skip comments. Document the *why* and the non-obvious; never the *what* the code already shows.

## Phase 1: Decide what actually needs documenting

1. **Read the target** — the file, module, or diff the user named (default to the current change if they named nothing). Read enough of the surrounding code to know what a reader could already infer.
2. **Match the repo's existing doc style.** Read a few already-documented files: docstring convention (Google / NumPy / reST / JSDoc / TSDoc), whether public APIs carry docstrings, how module headers look. Match it exactly — don't introduce a new style.
3. **Select ruthlessly.** Document something only if it clears this bar:
   - **Public API surface** — an exported function/class/module whose contract (params, return, raises, side effects) a caller needs and can't see from the body.
   - **Non-obvious *why*** — a workaround, an invariant, a performance trade-off, an ordering dependency, a link to an issue/spec that explains a surprising choice.
   - **A gotcha** — behavior that would surprise a competent reader (a subtle edge case, a footgun, a "must call X before Y").

   If a candidate doesn't clear the bar, **leave it undocumented** — that is the correct outcome, not a gap. Say plainly which things you deliberately left alone and why.

## Phase 2: Write it

1. **Comments/docstrings: explain intent, not mechanics.** A single line is usually enough. Never narrate steps ("loop over the items"), restate the signature, or echo a name. If the clearest fix is a better name instead of a comment, suggest that.
2. **Docstrings: state the contract concisely** — what it does, its params/return, and what it raises or mutates — in the repo's format. Skip the obvious; a one-line summary is fine when that's all the contract is.
3. **README / guide prose:** lead with what the reader needs to do or know; keep examples runnable and current; don't duplicate what's already documented elsewhere — link instead.
4. **Don't change code behavior.** This skill writes documentation. If documenting reveals a bug or a confusing API, report it (for the debug or refactor skill) rather than fixing it here.

## Phase 3: Verify

- **Re-read each doc against the code it describes** — an inaccurate comment is worse than none. Confirm params, return types, and described behavior actually match.
- If the repo builds docs (e.g. Sphinx, TypeDoc, mkdocs — check CLAUDE.md), build them to confirm nothing is malformed.

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

## Rules

- **Bias toward less.** When unsure whether something needs a comment, it doesn't. Under-documenting is a smaller sin than comment noise.
- One-line comments by default; reserve multi-line docstrings for genuine public-API contracts.
- Never add changelog/narration comments ("Added to fix…", "Now we handle…") or comments that restate the code.
- Don't document code you didn't read fully — a plausible-but-wrong doc is a trap for the next reader.
- Keep docs next to the code they describe; don't spawn a separate doc file when a docstring would do.

## When NOT to use

- The user wants code written or changed — that's implement/refactor; this skill only writes docs.
- The user wants a PR description or release notes — use the pr or release skill.
- The code is self-explanatory and the user just feels it "should have comments" — say so; adding noise to clear code makes it harder to read, not easier.
