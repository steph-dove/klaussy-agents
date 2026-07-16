---
name: fastapi-deps
description: Use when the user wants to upgrade the project's dependencies safely — bump versions, read changelogs for breaking changes, and verify the suite still passes. Upgrades incrementally and stops on the first break; it does not add new dependencies (that's a design decision to raise separately).
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

Whatever you output for the user (comments, descriptions, messages) must read as if a human engineer wrote it. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

- **No em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite. This is the single biggest AI tell.
- **No filler openers.** Cut "It's worth noting that", "It's important to note that", "I noticed that", "I wanted to point out that", "Please note that", "Just to mention", "Worth noting", "Note that". State the point directly.
- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps", "Feel free to...", "Happy to help", "Let me know your thoughts".
- **Tighten hedges.** "in order to" → "to"; "could potentially" → "could"; "may potentially" → "may". Drop stacked qualifiers.
- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**
- **No excessive apologies.** Avoid apologetic filler ("Sorry about that!", "My apologies for the confusion", "Apologies for the oversight"). State the correction or resolution directly.
- **Prefer active, imperative verbs and avoid narration.** Use direct instructions (e.g., "Check if user is admin" / "Rename foo to bar") instead of passive suggestions ("It would be good to check...", "You might want to rename..."). Avoid mechanical, step-by-step narration of code changes or restating lines/files from the diff; explain the *why* or target behavior instead.
- **Avoid the LLM lexicon & buzzwords.** Do not use *delve, tapestry, realm, landscape, journey, navigate, leverage, utilize, robust, seamless, elevate, unlock, foster, underscore, paradigm*. Replace corporate jargon (e.g. leverage/utilize) with simpler words (e.g. use).
- **Avoid transition crutches.** Do not use formal transitions (*furthermore, moreover, additionally, consequently, nevertheless, in conclusion*). Use simpler ones or prune them entirely.
- **Avoid rhetorical reframes and standalones.** Avoid the negation-reframe ("not only... but also", "this isn't just a bug fix — it's...") and standalone summary lines ("And that's the whole point.").
- **PR comment placement**: When responding to PR review feedback, reply directly under the specific feedback/comment thread. Do not post replies in a separate/new top-level comment.
- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **No superlatives or ranking praise.** Don't editorialize a point's importance: cut "this is the sharpest catch in the review", "best catch", "great find", "excellent point", "the most important issue here". Rating a comment against the others is an AI tell and adds nothing. State the substance and stop.
- **Don't mirror the thread's tone.** When you reply to an existing comment, review note, or message, read it for substance but not for temperature: neutralize any rudeness or bluntness in it before you draft. Hostile or curt input must not prime a hostile or curt reply, answer as if the other person had phrased it civilly.
- **Don't thank a bot.** When the reviewer is an automated tool or bot (a review bot, another agent, a CI check), respond to the substance without gratitude or pleasantries aimed at it, no "thanks for the review", "good catch", or addressing it as a person. Reserve those for a human reviewer, and even then keep them minimal.
- **Be short, then cut more.** Lead with the point. Keep the decision and the one fact that justifies it, then stop. A reply in a thread is usually one sentence; a single review comment one to five. Don't pad to sound thorough or stack throat-clearing ahead of the point.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop detail the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact; drop what's merely supporting. This is the one place humanizing may drop content, never reverse or invent meaning, but you need not preserve every clause.
- Vary sentence shape; don't open every line the same way. Never reword code, identifiers, or anything inside backticks or fences. Humanize prose only.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Good call, done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: Good call. `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

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
