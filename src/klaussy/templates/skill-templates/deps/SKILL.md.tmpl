---
name: {{REPO}}-deps
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

{{HUMANIZE}}

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
