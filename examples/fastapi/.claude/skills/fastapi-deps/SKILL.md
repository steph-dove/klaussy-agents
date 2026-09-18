---
name: fastapi-deps
description: Use when the user wants to upgrade the project's dependencies safely — bump versions, read changelogs for breaking changes, and verify the suite still passes. Upgrades incrementally and stops on the first break; it does not add new dependencies (that's a design decision to raise separately).
allowed-tools: Read Grep Glob Bash Edit
---

Upgrade dependencies without breaking the build. Move in small, verifiable steps — one batch at a time, tests green after each — rather than bumping everything at once and debugging the pile.

## Phase 1: Survey

1. **Read CLAUDE.md** for the package manager, the install command, and the test command.
2. **Read the manifest** (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, …) and the lockfile. Note which versions are pinned exactly vs. ranged, and which deps are runtime vs. dev.
3. **List what's outdated.** Use the ecosystem's own tool (`pip list --outdated`, `npm outdated`, `go list -m -u all`, `cargo outdated`). Separate the upgrades into:
   - **patch/minor** — low risk, batchable.
   - **major** — has breaking changes; handle one at a time.
4. **Confirm a green baseline first.** Run the test suite *before* changing anything. If it's already red, stop — you can't attribute a later failure to an upgrade.

## Phase 2: Upgrade in order of risk

1. **Patch/minor first, as one batch.** Bump them, reinstall, run the full suite. If green, keep going. If red, narrow to the culprit (bisect the batch) before proceeding.
2. **Then majors, one at a time.** For each major bump:
   - **Read its changelog / migration notes** for the version range you're crossing — grep the codebase for the APIs it says changed, and check whether you use them.
   - Apply the bump and any required code changes together.
   - Run the suite. Only move to the next major once green.
3. **Respect the pinning style.** If the repo pins exact versions, pin the new exact version; if it uses ranges, keep the range form. Update the lockfile with the manager's own command — never hand-edit a lockfile.

## Phase 3: Verify and summarize

1. **Run the full suite, lint, and build** one final time on the fully-upgraded tree.
2. **Summarize** what moved: package, old → new version, and for any major bump, the one-line reason it was safe (or the code change it required). Flag anything you couldn't fully verify.

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

**The scrubber is not the humanize pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

## Rules

- Do NOT add new dependencies or remove existing ones — this skill upgrades what's already declared. A new dependency is a decision to raise with the user, not to slip into an upgrade.
- Do NOT bump past a major boundary without reading that library's breaking-change notes and checking your usage against them.
- Never hand-edit the lockfile; regenerate it through the package manager so the resolution stays consistent.
- If an upgrade needs code changes beyond a trivial rename, make the minimal change to adapt — don't refactor surrounding code while you're in there.
- If a security advisory is the reason for the upgrade, prioritize that package and call it out explicitly.

## When NOT to use

- The user wants to add a brand-new dependency — that's a design choice; discuss the trade-off first, don't route it through here.
- A single dependency needs a deep, involved migration (a framework major with wide surface) — treat that as its own planned task with the plan/implement skills.
- The "upgrade" is really a lockfile refresh with no version changes — just regenerate the lockfile; you don't need this flow.
