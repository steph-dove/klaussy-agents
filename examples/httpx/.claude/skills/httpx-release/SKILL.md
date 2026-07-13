---
name: httpx-release
description: Use when the user wants to cut a release — bump the version, update the changelog from conventional commits, and tag. Detects where the version lives, derives the next version from the commits since the last tag, and stages the release locally; it does not push or publish unless explicitly asked.
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

- Never publish, push tags, or upload to a registry without explicit confirmation in this request.
- Keep the version consistent across every declaring file — the top failure mode is a half-bumped release.
- The changelog describes user-facing impact, not a commit-by-commit transcript. Fold trivial commits together; drop pure-noise ones.
- If the working tree is dirty with unrelated changes, stop and ask — a release commit should contain only the bump and changelog.

## When NOT to use

- The user wants a single PR description — use the pr skill.
- There are uncommitted feature changes still in progress — finish and merge those first; a release tags an existing state.
- The project has no version declaration anywhere and no tags — clarify what "release" means here before inventing a scheme.
