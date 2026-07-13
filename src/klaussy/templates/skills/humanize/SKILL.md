---
name: {{REPO}}-humanize
description: Use when the user wants prose, comments, docs, or a file's text to read like a human engineer wrote it instead of an AI. Strips AI tells (em-dashes, filler openers, chatbot scaffolding) by rewriting, then runs klaussy's deterministic scrubber as a guaranteed backstop. Never touches code.
allowed-tools: Read Grep Glob Bash Edit
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, humanize the prose the user pasted into the conversation. Otherwise treat `$ARGUMENTS` as one or more file paths (or a glob) and humanize the prose in those files in place.

{{HUMANIZE}}

## Steps

1. **Get the prose.** For file targets, Read each file. For pasted text, work with what's in the conversation. If the text is a reply inside a thread (a review comment, a message chain), the surrounding comments are read-only context: take their substance, neutralize their tone in your head, and humanize only your own message. Don't carry the thread's bluntness or rudeness into what you write — see "Don't mirror the thread's tone" above.
2. **Rewrite by the rules above.** This is the judgment pass: kill filler openers, drop chatbot scaffolding, replace em/en dashes, tighten hedges, vary sentence shape. Only touch prose, never code, identifiers, or anything inside backticks or fences.
3. **Run the deterministic backstop.** klaussy ships a code-preserving scrubber that guarantees the high-confidence tells are gone regardless of the rewrite. This is the post-processing step, always run it last:
   - **Files:** `klaussy humanize <file>... --write` (rewrites in place; prints which files changed).
   - **Pasted text:** pipe the rewritten text into `klaussy humanize` on stdin and use its output (on macOS/Linux, e.g. `printf '%s' "$text" | klaussy humanize`; on Windows use the shell's own piping — the point is stdin in, humanized text out).
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
