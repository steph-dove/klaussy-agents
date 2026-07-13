---
name: httpx-qa
description: Use when the user wants the current change QA'd and PR-ready evidence captured. Classifies the diff and runs the verification that actually fits it — screenshots for UI/frontend changes, endpoint or e2e runs for backend, command output for a CLI, tests for a library — then saves artifacts and writes a QA summary. Right-sizes QA to the change; it does not write features or fix bugs.
allowed-tools: Read Grep Glob Bash Edit Write
---

QA the current change and capture evidence a reviewer can trust. The point is to run *the QA that's valid for this change* — a UI tweak needs screenshots, a backend fix needs the endpoint exercised and the suite run, a CLI change needs its commands run. Don't screenshot a database migration; don't run the full browser e2e suite for a one-line helper.

## Steps

1. **Read CLAUDE.md** for how this project builds, runs, and tests, plus any e2e/screenshot tooling it already has. **Read any `.claude/rules/*.md`** whose `paths:` glob covers the changed files — they often name the ports, fixtures, or QA conventions for that layer.
2. **See what changed.** `git diff master...HEAD` for the branch's work, plus `git diff` / `git diff --cached` for uncommitted edits. **Classify each surface the diff touches** (a change can span more than one — QA each with its own method):
   - **UI / frontend** — components, styles, templates, pages, client-side behavior.
   - **Backend / API / service** — routes, handlers, business logic, jobs, DB.
   - **CLI / tool** — command entrypoints, flags, output.
   - **Library / SDK** — importable code with no runtime surface of its own.
   - **Docs / config / infra only** — no runtime behavior to observe.
3. **Run the QA that fits each surface** (use **`httpx-run`** whenever you need to bring the app or service up):
   - **UI / frontend** → **capture screenshots.** Prefer the repo's own tooling (Playwright, Cypress, Storybook, a visual-test harness) — it already knows how to reach each screen. Otherwise launch the app via `httpx-run` and drive a headless browser (Playwright/Puppeteer) if one is installed. Capture the states the change actually affects: the default view, the changed interaction, and empty/error or responsive breakpoints when layout or state handling changed. Grab a *before* shot from `master` too when the branch point is cheap to check out, so the diff is visible. Note what changed visually.
   - **Backend / API / service** → run the test suite and any integration/e2e that covers the area, then **exercise the changed path for real**: bring the service up, hit the endpoint (curl/httpie/the project's client), and capture the request → response and any relevant log lines.
   - **CLI / tool** → run the representative commands that exercise the change (not just `--help`); capture stdout, stderr, and exit codes.
   - **Library / SDK** → run the unit tests plus a small usage snippet that calls the changed API.
   - **Docs / config / infra only** → there's nothing to observe at runtime. Say so and stop — don't manufacture QA.
4. **Save the artifacts where the user can actually open them** — a subfolder named `<repo>-<branch>` inside their Downloads folder (e.g. `myapp-feature-login/`), so screenshots land somewhere they'll look. Resolve the destination for the OS you're on:
   - **macOS / Linux**: `~/Downloads/<repo>-<branch>/`
   - **Windows**: `%USERPROFILE%\Downloads\<repo>-<branch>\` (PowerShell: `$env:USERPROFILE\Downloads\...`)

   Derive `<repo>` from the repo root's folder name and `<branch>` from the current branch (`git rev-parse --show-toplevel` and `git rev-parse --abbrev-ref HEAD`), replacing any `/` in the branch with `-` so it's one valid folder name. Create the folder if it doesn't exist, then write screenshots as PNGs and captured command/HTTP output as text into it — keep artifacts out of the repo tree; they're evidence for a human, not source to commit. If there's no Downloads folder (a headless CI box), fall back to the user's home directory. Report the absolute folder path so the user can find it.
5. **Write a QA summary** suited to drop into a PR's Test Plan / QA section: which surfaces changed, what QA ran for each, the evidence (screenshot paths, captured output, test results), pass/fail, and anything you could NOT cover and why. Lead with the result, keep it tight.

## Rules

- **Right-size QA to the diff.** Only exercise what the change touches. A reviewer doesn't need forty screenshots or a full e2e run for a two-line fix — capture the states that actually changed, and skip surfaces the diff doesn't reach.
- **Never fabricate evidence.** If you can't capture a screenshot (no browser tooling, no display, no fixture data), say so plainly and give the manual repro steps a human would follow — a described gap beats a faked artifact.
- **Don't change code to make QA pass.** A failure here is a real signal — that's a bug for the debug skill, not something to patch around. Report it.
- **Local / dev only.** Never QA against production or with production credentials unless the user explicitly says so. Tear down any app or server you started.

## When NOT to use

- The change has no runtime surface — pure docs, comments, or a refactor with green tests. There's nothing to observe; don't force it.
- The user wants tests *written* — use **`httpx-test`**. QA runs and observes; it doesn't author test code.
- The user wants a bug *fixed* — use **`httpx-debug`**, then come back here to capture the fix working.
