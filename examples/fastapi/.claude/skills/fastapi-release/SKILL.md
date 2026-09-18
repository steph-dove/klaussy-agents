---
name: fastapi-release
description: Use when the user wants to cut a release — bump the version, update the changelog from conventional commits, and tag. Detects where the version lives, derives the next version from the commits since the last tag, and stages the release locally; it does not push or publish unless explicitly asked. Also known as `klaussy-release`.
allowed-tools: Read Grep Glob Bash Edit Write
disable-model-invocation: true
---

Cut a release: pick the next version, update every place the version is declared, write the changelog from the conventional commits since the last release, and tag. Stop before pushing or publishing unless the user asked for those too.

## Phase 1: Establish the baseline

1. **Find the current version and every file that declares it.** Read CLAUDE.md for the version location, then confirm by searching — a project often repeats the version in more than one file (e.g. `pyproject.toml` *and* `src/<pkg>/__init__.py`, or `package.json` *and* a lockfile). List them all; a release that bumps one and misses another ships an inconsistent version.
2. **Find the last release tag.** `git describe --tags --abbrev=0` (fall back to the first commit if there are no tags). This is the range boundary for the changelog.
3. **Collect the commits since that tag.** `git log <last-tag>..HEAD --oneline`. If there are none, there's nothing to release — say so and stop.

## Phase 2: Choose the next version

Derive the bump from the conventional-commit types in the range (semver):

- **major** — any commit with a `!` (e.g. `feat!:`) or a `BREAKING CHANGE:` footer.
- **minor** — at least one `feat:` and no breaking change.
- **patch** — only `fix:` / `perf:` / `refactor:` / `docs:` / `chore:` etc.

State the computed version and the reason before changing anything. If the user named a specific version, use theirs; if the commits disagree with it (e.g. they said patch but there's a `feat!`), flag the mismatch and let them decide.

## Phase 3: Apply the bump

1. **Update the version in every file** found in Phase 1 — edit the literal, don't reformat the file.
2. **Update the changelog.** If a `CHANGELOG.md` exists, follow its existing format exactly; otherwise create one in the Keep a Changelog style. Add a new section for this version dated with the real date (run `date +%F` — do not guess it). Group entries by type (Added / Fixed / Changed / Removed) from the commit subjects; write them for a human reader, not as raw commit lines.
3. **Do not touch anything unrelated to the release.**

## Phase 4: Verify, commit, tag

1. **Run the project's build/test/lint** (from CLAUDE.md) to confirm the bumped tree is releasable.
2. **Commit** the version + changelog changes with a `chore(release): v<version>` message (or the repo's release-commit convention if it has one).
3. **Tag** `v<version>` (match the repo's existing tag style — check `git tag` for a `v` prefix or not).
4. **Stop here and report** the version, the changelog section, and the exact push/publish commands (e.g. `git push && git push --tags`, `python -m build`, `npm publish`) — but do NOT run them unless the user explicitly asked to publish. Publishing is irreversible.

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

- Never publish, push tags, or upload to a registry without explicit confirmation in this request.
- Keep the version consistent across every declaring file — the top failure mode is a half-bumped release.
- The changelog describes user-facing impact, not a commit-by-commit transcript. Fold trivial commits together; drop pure-noise ones.
- If the working tree is dirty with unrelated changes, stop and ask — a release commit should contain only the bump and changelog.

## When NOT to use

- The user wants a single PR description — use the pr skill.
- There are uncommitted feature changes still in progress — finish and merge those first; a release tags an existing state.
- The project has no version declaration anywhere and no tags — clarify what "release" means here before inventing a scheme.
