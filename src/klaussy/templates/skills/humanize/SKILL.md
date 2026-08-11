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

**Get the prose first.** For file targets, Read each file. For pasted text, work with what's in the conversation. If the text is a reply inside a thread (a review comment, a message chain), the surrounding comments are read-only context: take their substance, neutralize their tone in your head, and humanize only your own message. Don't carry the thread's bluntness or rudeness into what you write — see "Don't mirror the thread's tone" above.

Then run four passes, in this order, each as its own turn. Doing it in one pass is what makes the output read like a tidied-up model draft: with every rule in play at once, the ones that survive are the safe mechanical ones, and voice and length lose. **One job per pass. Do not do a later pass's job early.**

### Pass 1 — Cut (content only, no restyling)

Rules that apply: **Answer what was asked, then stop** and **Shape**, above. Nothing else.

Delete whole sentences and paragraphs that don't earn their place: the closing principle, the mechanism nobody asked about, the point already made, the summary of what you just said. **Keep every sentence you keep word for word.** If you find yourself improving a sentence, stop — that's pass 2.

For a reply, the question being answered is the yardstick. Write it down first if it isn't obvious, then cut anything that doesn't answer it.

### Pass 2 — Voice (register only, no content change)

Rules that apply: **Voice** and **Stay civil while you cut**, above. Nothing else.

Say each line out loud and write that version. Contractions in, noun phrases back into verbs, plain short words, a named subject doing the work, a stance where there is one. Fragments are fine. Let the rhythm be uneven.

**Every fact that goes into this pass comes out of it.** No new claims, none dropped, none softened or strengthened. If a sentence seems worth deleting here, you missed it in pass 1; leave it.

### Pass 3 — Check (did the meaning survive?)

Put the pass 2 output next to the original and compare claim by claim:

- **Added** — anything asserted that the original didn't say, including a hedge that became a certainty, or agreement the author never gave.
- **Dropped** — a load-bearing noun, number, identifier, file path, or version. "We invalidated on every write" lost `the cache`, and that's a failure even though it reads fine.
- **Reversed** — a concession that became a refusal, "may race" that became "races", or a point that changed sides.

Fix what you find by restoring the original's meaning in the pass 2 voice. State plainly what you restored. If nothing changed meaning, say that in one line and move on.

### Pass 4 — Scrub (deterministic backstop)

klaussy ships a code-preserving scrubber that guarantees the high-confidence tells are gone regardless of the rewrite. Always run it last:

- **Files:** `klaussy humanize <file>... --write` (rewrites in place; prints which files changed).
- **Pasted text:** pipe the pass 3 output into `klaussy humanize` on stdin and use its output (on macOS/Linux, e.g. `printf '%s' "$text" | klaussy humanize`; on Windows use the shell's own piping — the point is stdin in, humanized text out).
- If the `klaussy` CLI isn't on PATH, run it via `python -m klaussy humanize ...`. If neither resolves, say the deterministic backstop was unavailable and that only the rewrite was applied.

Then **report** what changed: for files, the list the scrubber reported; for text, show the humanized result.

### When one pass is enough

A single sentence or a one-line comment doesn't need four turns. Below roughly 40 words there's nothing to cut and no structure to break, so do pass 2 and pass 4 and say you skipped the rest. Everything longer gets all four.

## Rules

- The deterministic scrubber is a conservative subset (dashes, a fixed set of openers/scaffolding, a few hedges, *actual*/*actually*). Your rewrite does the broader work the scrubber can't; the scrubber then guarantees the conservative tells. Run both, not just one.
- Don't collapse the passes to save a turn. Cutting and restyling in one go is how a rewrite ends up neither shorter nor more human, and merging the check into the voice pass means the pass that changed the meaning is the one grading it.
- Appeals to consensus ("most people expect...", "everyone does it this way") are a rewrite-only fix too. Don't just soften them into "many teams" — either cite what the claim rests on (the code, a repo convention, a link) or make it your own view. Dropping the claim entirely is fine when the sentence stands without it.
- *real*, *really*, *genuinely*, and *truly* are the rewrite's job, not the scrubber's — it leaves them alone because "real user data" sometimes contrasts with fixtures. Cut them where they only add emphasis ("real work" is "work"), keep them where they carry that contrast.
- Preserve the decision and its rationale; never reverse, add, or invent meaning. Humanizing is mostly a tone/style edit, but brevity may drop low-value detail (explanatory parentheticals, restated identifiers, narration the diff already shows). Keep the load-bearing facts, cut what the reader can reconstruct (see "Cut detail, not just words" above).
- Never reword code, identifiers, fenced ```blocks```, or `inline code`. The scrubber already skips them; you must too.
- Don't "improve" prose beyond the voice pass, removing AI tells, keeping it civil (see "Don't let trimming tip into terse" above), and tightening length (see "Budgets" above) unless the user asks. Match the surrounding voice — a slightly blunt author stays slightly blunt, you only stop the trim from making them ruder.
- Shortest form that carries the decision. A reply in a thread should aim for one sentence; a single review comment one to three. If it runs long, cut detail the reader doesn't need, don't just compress what you said into denser prose.
- Structure is a tell too. A three-sentence answer wearing headings, a bold field label per line, or a bullet list of one is AI-shaped no matter how the sentences read. Flatten it to prose unless the target format (a PR template, a changelog, an ADR) calls for the structure.
- Use `klaussy humanize <file> --check` (exit 1 if anything would change, no writes) when the user only wants to know whether a file reads as AI-written.

## When NOT to use

- The user wants code changed, refactored, or fixed — use the implement, refactor, or fix skill.
- The user wants a review of the writing's substance, not its tells — that's a different request.
- The text is already plain and human; running the scrubber will report no changes, which is a valid outcome.
