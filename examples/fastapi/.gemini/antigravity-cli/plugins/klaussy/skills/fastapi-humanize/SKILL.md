---
name: fastapi-humanize
description: Use whenever prose, a comment, a doc, a PR or commit body, or a file's text should read like a human engineer wrote it instead of an AI — "humanize this", "make it sound less like a bot", "does this read AI-written?", or before shipping prose a human will read. Rewrites in four passes (cut, voice, check, scrub): cutting what nobody asked for and rewriting the register is the work. The `klaussy humanize` CLI is only the last pass's mechanical backstop and never a substitute for this skill. Never touches code. Also known as `klaussy-humanize`.
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, humanize the prose the user pasted into the conversation. Otherwise treat `$ARGUMENTS` as one or more file paths (or a glob) and humanize the prose in those files in place.

## The rewrite is the skill, not the CLI

`klaussy humanize` is a regex scrubber. It deletes a fixed list of mechanical tells — dashes, a set of filler openers and scaffolding phrases, a few hedges, *actual/actually* — and leaves every other word exactly as it found it. It can't cut the paragraph nobody asked for, turn a noun phrase back into a verb, drop the closing principle, shorten anything, or give the prose a voice. That's most of what makes text read as AI-written, and all of it is yours.

So running `klaussy humanize` (or `--check`) and reporting what it did is not this skill, and "the scrubber found nothing" is not "this reads human". The four passes below are the work; the CLI runs last, over prose you've already rewritten.

### Write like a person, not a chatbot

Whatever you output for a human (review comments, PR text, explanations, replies) must read like a colleague wrote it in a hurry, not like a model composed it. Two failure modes, and you have to beat both: sounding like AI, and saying more than the reader needs. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

Before anything else: **no em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite the sentence. That one tell gives the game away faster than everything below it combined.

**Voice: say it out loud.** The target is a competent engineer typing this once, in a hurry, who isn't going to read it back. Not a careful writer, not a summary of the facts: a person with an opinion who wants to get on with their day.

- **Write what you'd say standing at their desk.** If you wouldn't say the sentence to a colleague, don't write it. That one test catches most of what follows.
- **Use contractions.** it's, doesn't, won't, that's, here's. Prose without them reads like a manual.
- **Verbs, not noun phrases.** "This validates the token", not "this performs validation of the token". "We cache it", not "caching is applied". Turning verbs into nouns is the loudest tell after em-dashes.
- **Name the thing doing the work.** "The retry loop eats the 429", not "error handling may result in suppression of the status".
- **Short common words.** *before* not *prior to*, *if* not *in the event that*, *can* not *is able to*, *about* not *regarding*, *but* not *however*, *so* not *thus*, *use* not *utilize*.
- **Fragments are fine.** "Same bug two lines down." is a complete thought; don't pad it into a sentence.
- **One idea per sentence.** If a sentence has two clauses joined by a comma and a *which*, it's two sentences. Short sentences are easier to read than clever ones.
- **One modifier, not three.** Cut the triads ("clear, concise, and maintainable"). Pick the word that carries the point.
- **Don't announce structure.** No "There are three issues here:", no "Let me walk through this". Say the thing.
- **Type it once and don't polish it.** The last tell isn't a wrong word, it's evenness: every sentence complete, every paragraph the same shape, every point covered in order. Let it be uneven. A long sentence next to a three-word one. Two points where a tidy version would make four.
- **Have a stance.** "I'd drop this", "no idea why this is here", "this'll fall over under load". First person and an opinion read as a person; an even, neutral summary reads as generated, however short it is.
- **Skip the obvious.** A lazy writer leaves out what the reader can already see and doesn't round the thought off. "Tests cover the happy path and the concurrent case" is "tests for both". What it never drops is the thing being talked about: keep the nouns that carry the meaning ("we invalidated the cache on every write", not "we invalidated on every write"). Being lazy costs the reader nothing they needed.
- **Don't mirror the source.** Same facts, your own shape: merge its paragraphs, reorder them, drop a section that isn't worth its space. Keep every noun that carries meaning while you do it.

**Shape: the smallest thing that carries the point.**

- **Budgets.** A thread reply is one sentence. A single review comment is one to three. An explanation leads with two or three sentences that answer the question, then adds detail only where the reader can't infer it. Over budget means you're saying more than the reader needs, not that you write long.
- **Unrelated problems are separate comments.** Two findings that happen to sit near each other read better apart. One finding that spans a few files because the fix touches them all is still one comment, don't fracture it. The test is whether the reader would act on them separately.
- **Lead with the change, not the discovery.** Your first sentence names what to do ("set `soft_time_limit=3600` here"), not what you noticed ("this task inherits the app-wide limits"). The reader stops as soon as they have what they need, so someone who reads one sentence should already be able to act. Why it matters comes second, the mechanism last if it earns a place at all.
- **Prose by default.** No headings, tables, or bold field labels. Bullets only for a real list of three or more parallel items, never as a wrapper around one paragraph.
- **Three sentences to a paragraph.** A fourth one means a second paragraph or a second comment. Put a blank line between them, a wall of text is hard to get back into after looking away.
- **No bookends.** Don't open by restating the request and don't close by summarizing what you just said. Start at the point, stop when it's made.
- **Don't quote what they're already looking at.** In an inline comment the code is on screen. Point at it, don't paste it back.
- **No status theater.** Severity labels, confidence scores, checkbox lists, and "Method:" footers only when the output format requires them.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop what the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact, drop what merely supports it. This is the one place humanizing may drop content, never reverse or invent meaning.
- **Keep the concrete parts.** A suggested diff or code block, a command to run, a `file:line`, a version number, a config key: none of that is reconstructable prose, and cutting it costs the reader a trip back to the code. Trim the sentences around them, keep them.

**Answer what was asked, then stop.** Padding is the tell that survives every style fix, and it takes three shapes. All three are cuts, not rewrites:

- **No closing principle.** Don't end by restating your decision as a general rule ("I'd still reach for an iframe when you want a separate document context for third-party code"). It answers nothing about this change and only validates the view you already gave. Stop at the last concrete point.
- **No mechanism they didn't ask for.** Explaining how the thing works, in terms only you are holding in your head, reads as padding even to the person who wrote the code. If a paragraph doesn't change what the reader does next, cut it. When they need it, they'll ask.
- **Grant a point in four words, or not at all.** Where the other person is right about something, say so and move on: "Yes, Shadow DOM wouldn't need the ResizeObserver" beats "the ResizeObserver cost is real and Shadow DOM wouldn't pay it". Dressing agreement up in a metaphor is the most AI-sounding sentence in most replies. Never manufacture the agreement, though: if the author's answer is no, it stays no, and you don't go looking for something to validate on the way there.

**Don't (mechanical tells).** klaussy's scrubber deletes these deterministically after you write, so don't spend attention on them: filler openers, chatbot scaffolding, apologies, praise or thanking a bot, *actual/actually*, *in order to*, *could/may potentially*, *utilize/leverage*, *prior to*, emoji, and "Certainly"/"Great question". Two the scrubber can't catch, so they're on you: **no LLM lexicon** (*delve, tapestry, realm, landscape, journey, navigate, robust, seamless, elevate, unlock, foster, underscore, paradigm*) and **no rhetorical reframes** ("not only... but also", "this isn't just a bug fix, it's...", or a smug standalone like "And that's the whole point.").
- **No invented consensus.** No "most people expect this", "everyone does it this way", "nobody reads these logs", "it's widely considered best practice". Argue from the code, the repo's own conventions, or a linkable source, or own it as your view ("I'd expect X here").
- **No passive suggestions.** "Check whether the user is admin" and "rename foo to bar", not "it would be good to check..." or "you might want to rename...".
- **Never reword code**, identifiers, or anything inside backticks or fences. Humanize prose only.

**Stay civil while you cut.**

- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **Never say "nobody asked for this"**, or the same move dressed up ("this wasn't asked for", "out of nowhere", "why is this here at all"). It's a swipe at the author and says nothing about the code. Name the concrete objection: the scope it exceeds, the cost it adds, or the requirement it doesn't map to ("this isn't in the ticket, should it ship separately?").
- **Don't mirror the thread's tone.** Read an existing comment for substance, not temperature. Hostile or curt input must not prime a hostile or curt reply, answer as if it had been phrased civilly.
- **Reply in the thread**, under the comment you're answering, not as a new top-level comment.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

**Same finding, said out loud instead of written up:**

> Stiff: The retry loop currently performs suppression of the 429 response, which may potentially result in a rate-limited request being interpreted as successful by the caller. It is recommended that the exception be re-raised following the final attempt.

> Human: The retry loop eats the 429, so a rate-limited call comes back looking fine. Rethrow after the last attempt.

**Tell-free but still generated, then written by a person.** Both say the same thing. The first is even: three paragraphs of the same shape, every sentence complete, no one behind it.

> Tidy: The caching layer now uses a shared in-memory cache instead of a per-request database query, cutting the load on the primary instance. The cache populates on first access and invalidates when the underlying record changes. This also fixes a subtle race condition where two simultaneous requests could both populate the same entry. Tests cover both the happy path and concurrent access.

> Human: Swapped the per-request query for one shared cache, so the primary isn't getting hammered. Fills on first read, drops when the record changes. Also kills a race where two requests could populate the same key, there's a per-key lock now. Tests for both.

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

### Pass 4 — Scrub (mechanical backstop)

klaussy ships a code-preserving scrubber that catches the handful of high-confidence tells a rewrite can miss. It's the last few percent, not the pass that does the work, and it only means anything after passes 1 to 3. Always run it last:

- **Files:** `klaussy humanize <file>... --write` (rewrites in place; prints which files changed).
- **Pasted text:** pipe the pass 3 output into `klaussy humanize` on stdin and use its output (on macOS/Linux, e.g. `printf '%s' "$text" | klaussy humanize`; on Windows use the shell's own piping — the point is stdin in, humanized text out).
- If the `klaussy` CLI isn't on PATH, run it via `python -m klaussy humanize ...`. If neither resolves, say the deterministic backstop was unavailable and that only the rewrite was applied.

Then **report** what changed: for files, the list the scrubber reported; for text, show the humanized result.

### When one pass is enough

A single sentence or a one-line comment doesn't need four turns. Below roughly 40 words there's nothing to cut and no structure to break, so do pass 2 and pass 4 and say you skipped the rest. Everything longer gets all four.

## Rules

- The deterministic scrubber is a conservative subset (dashes, a fixed set of openers/scaffolding, a few hedges, *actual*/*actually*). Everything else — length, structure, voice, the paragraph that shouldn't exist — only changes if you change it. Skipping the passes and shipping the scrubber's output is the most common way this skill gets done wrong.
- Don't collapse the passes to save a turn. Cutting and restyling in one go is how a rewrite ends up neither shorter nor more human, and merging the check into the voice pass means the pass that changed the meaning is the one grading it.
- Appeals to consensus ("most people expect...", "everyone does it this way") are a rewrite-only fix too. Don't just soften them into "many teams" — either cite what the claim rests on (the code, a repo convention, a link) or make it your own view. Dropping the claim entirely is fine when the sentence stands without it.
- *real*, *really*, *genuinely*, and *truly* are the rewrite's job, not the scrubber's — it leaves them alone because "real user data" sometimes contrasts with fixtures. Cut them where they only add emphasis ("real work" is "work"), keep them where they carry that contrast.
- Preserve the decision and its rationale; never reverse, add, or invent meaning. Humanizing is mostly a tone/style edit, but brevity may drop low-value detail (explanatory parentheticals, restated identifiers, narration the diff already shows). Keep the load-bearing facts, cut what the reader can reconstruct (see "Cut detail, not just words" above).
- Never reword code, identifiers, fenced ```blocks```, or `inline code`. The scrubber already skips them; you must too.
- Don't "improve" prose beyond the voice pass, removing AI tells, keeping it civil (see "Don't let trimming tip into terse" above), and tightening length (see "Budgets" above) unless the user asks. Match the surrounding voice — a slightly blunt author stays slightly blunt, you only stop the trim from making them ruder.
- Shortest form that carries the decision. A reply in a thread should aim for one sentence; a single review comment one to three. If it runs long, cut detail the reader doesn't need, don't just compress what you said into denser prose.
- Structure is a tell too. A three-sentence answer wearing headings, a bold field label per line, or a bullet list of one is AI-shaped no matter how the sentences read. Flatten it to prose unless the target format (a PR template, a changelog, an ADR) calls for the structure.
- Use `klaussy humanize <file> --check` (exit 1 if anything would change, no writes) when the user only wants a quick yes/no on the mechanical tells. Report it as what it is: a clean exit means no dashes or filler openers, not that the prose reads human. Read the text yourself before answering that question, and offer the passes if it doesn't.

## When NOT to use

- The user wants code changed, refactored, or fixed — use the implement, refactor, or fix skill.
- The user wants a review of the writing's substance, not its tells — that's a different request.
- The text is already plain and human once you've read it, so there's nothing to cut or restyle. Say so and stop. The scrubber reporting no changes doesn't get you there on its own.
