---
name: fastapi-release
description: Use when the user wants to cut a release — bump the version, update the changelog from conventional commits, and tag. Detects where the version lives, derives the next version from the commits since the last tag, and stages the release locally; it does not push or publish unless explicitly asked. Also known as `klaussy-release`.
allowed-tools: Read Grep Glob Bash Edit Write
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

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

## Rules

- Never publish, push tags, or upload to a registry without explicit confirmation in this request.
- Keep the version consistent across every declaring file — the top failure mode is a half-bumped release.
- The changelog describes user-facing impact, not a commit-by-commit transcript. Fold trivial commits together; drop pure-noise ones.
- If the working tree is dirty with unrelated changes, stop and ask — a release commit should contain only the bump and changelog.

## When NOT to use

- The user wants a single PR description — use the pr skill.
- There are uncommitted feature changes still in progress — finish and merge those first; a release tags an existing state.
- The project has no version declaration anywhere and no tags — clarify what "release" means here before inventing a scheme.
