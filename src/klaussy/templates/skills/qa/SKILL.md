---
name: {{REPO}}-qa
description: Use when the user wants the current change QA'd and PR-ready evidence captured. Classifies the diff and runs the verification that actually fits it — screen recordings and screenshots for UI/frontend changes, endpoint or e2e runs for backend, command output for a CLI, tests for a library — then saves artifacts and writes a QA summary. Right-sizes QA to the change; it does not write features or fix bugs.
allowed-tools: Read Grep Glob Bash Edit Write
---

QA the current change and capture evidence a reviewer can trust. The point is to run *the QA that's valid for this change* — a UI tweak needs a recording of the interaction plus screenshots, a backend fix needs the endpoint exercised and the suite run, a CLI change needs its commands run. Don't screenshot a database migration; don't run the full browser e2e suite for a one-line helper.

**Record the change in motion whenever you can.** A screen recording shows a reviewer what a still frame can't — the interaction, the transition, the loading and error states, the thing actually working end to end. Whenever the surface you're QA'ing has motion or a multi-step flow, capture video first and pull stills from it (or take them alongside); fall back to screenshots only when recording isn't available.

## Steps

1. **Read CLAUDE.md** for how this project builds, runs, and tests, plus any e2e, screenshot, or video-capture tooling it already has. **Read any `.claude/rules/*.md`** whose `paths:` glob covers the changed files — they often name the ports, fixtures, or QA conventions for that layer.
2. **See what changed.** `git diff {{BASE_BRANCH}}...HEAD` for the branch's work, plus `git diff` / `git diff --cached` for uncommitted edits. **Classify each surface the diff touches** (a change can span more than one — QA each with its own method):
   - **UI / frontend** — components, styles, templates, pages, client-side behavior.
   - **Backend / API / service** — routes, handlers, business logic, jobs, DB.
   - **CLI / tool** — command entrypoints, flags, output.
   - **Library / SDK** — importable code with no runtime surface of its own.
   - **Docs / config / infra only** — no runtime behavior to observe.
3. **Run the QA that fits each surface** (use **`{{REPO}}-run`** whenever you need to bring the app or service up):
   - **UI / frontend** → **record the flow, then capture screenshots.** Prefer the repo's own tooling (Playwright, Cypress, Storybook, a visual-test harness) — it already knows how to reach each screen, and most of it records video with one flag (see *Capturing a recording* below). Otherwise launch the app via `{{REPO}}-run` and drive a browser (Playwright/Puppeteer, or whatever browser-control tooling your agent surface has) with recording turned on. Record the change actually being used: the path a user takes through it, start to finish. Then capture stills for the states the change affects — the default view, the changed interaction, and empty/error or responsive breakpoints when layout or state handling changed. Grab a *before* recording or shot from `{{BASE_BRANCH}}` too when the branch point is cheap to check out, so the diff is visible. Note what changed visually.
   - **Backend / API / service** → run the test suite and any integration/e2e that covers the area, then **exercise the changed path for real**: bring the service up, hit the endpoint (curl/httpie/the project's client), and capture the request → response and any relevant log lines. If the change is visible through a UI or a dashboard, record that too.
   - **CLI / tool** → run the representative commands that exercise the change (not just `--help`); capture stdout, stderr, and exit codes. For anything interactive, long-running, or with meaningful terminal output (a TUI, a progress display, a prompt flow), record the terminal — `asciinema rec` if it's installed, otherwise a screen recording — so the reviewer sees the session rather than a transcript.
   - **Library / SDK** → run the unit tests plus a small usage snippet that calls the changed API.
   - **Docs / config / infra only** → there's nothing to observe at runtime. Say so and stop — don't manufacture QA.
4. **Save the artifacts where the user can actually open them** — a subfolder named `<repo>-<branch>` inside their Downloads folder (e.g. `myapp-feature-login/`), so recordings and screenshots land somewhere they'll look. Resolve the destination for the OS you're on:
   - **macOS / Linux**: `~/Downloads/<repo>-<branch>/`
   - **Windows**: `%USERPROFILE%\Downloads\<repo>-<branch>\` (PowerShell: `$env:USERPROFILE\Downloads\...`)

   Derive `<repo>` from the repo root's folder name and `<branch>` from the current branch (`git rev-parse --show-toplevel` and `git rev-parse --abbrev-ref HEAD`), replacing any `/` in the branch with `-` so it's one valid folder name. Create the folder if it doesn't exist, then write recordings as MP4 or WebM, screenshots as PNGs, and captured command/HTTP output as text into it — keep artifacts out of the repo tree; they're evidence for a human, not source to commit. Give each file a name that says what it shows (`login-error-state.png`, `checkout-flow.mp4`), and move recordings out of whatever temp directory the test runner dropped them in — Playwright and Cypress write videos under their own output folders and overwrite them on the next run. If there's no Downloads folder (a headless CI box), fall back to the user's home directory. Report the absolute folder path so the user can find it.
5. **Write a QA summary** suited to drop into a PR's Test Plan / QA section: which surfaces changed, what QA ran for each, the evidence (recording and screenshot paths, captured output, test results), pass/fail, and anything you could NOT cover and why. Say explicitly when a surface has no recording and why. Lead with the result, keep it tight.

## Capturing a recording

Work down this list and use the first option that's actually available — don't install new tooling just to record.

- **The repo's existing e2e/browser tooling**, which almost always records already:
  - **Playwright** — `use: { video: 'on' }` in `playwright.config`, or `browser.newContext({ recordVideo: { dir: '...' } })` in a standalone script. Writes WebM per context.
  - **Cypress** — records video by default for `cypress run`; check `videosFolder`.
  - **Puppeteer** — `page.screencast({ path: '...webm' })` (Chrome 126+), otherwise a burst of screenshots.
  - Storybook/visual harnesses, or any project-specific capture script.
- **Your agent surface's own browser control** — Claude in Chrome, Copilot's browser tooling, an IDE's integrated browser, or a browser-automation MCP server. If it can drive the page it can usually capture frames; use its recording feature if it has one, and a tight screenshot sequence at each step if it doesn't.
- **The browser itself** — Chrome DevTools Recorder to capture a flow, or the browser's built-in screen capture.
- **The OS**, when the change lives outside a browser (a desktop app, an installer, a TUI):
  - macOS: `screencapture -v ~/Downloads/<folder>/flow.mp4` (Ctrl-C to stop)
  - Linux: `ffmpeg -f x11grab -i :0.0 flow.mp4` (or the desktop's own recorder)
  - Windows: `ffmpeg -f gdigrab -i desktop flow.mp4`, or Xbox Game Bar (`Win+Alt+R`)
- **Terminal sessions** — `asciinema rec flow.cast`.

Keep recordings short and pointed: the flow the change affects, nothing else. Thirty seconds of the actual interaction beats five minutes of navigation. If none of these is available, say so in the summary and fall back to screenshots plus written repro steps.

## Rules

- **Right-size QA to the diff.** Only exercise what the change touches. A reviewer doesn't need forty screenshots or a full e2e run for a two-line fix — capture the states that actually changed, and skip surfaces the diff doesn't reach.
- **Record when recording is possible.** For anything with an interaction, a transition, or more than one step, a recording is the evidence; screenshots are the fallback, not the default. A still can't show that the flow works.
- **Never fabricate evidence.** If you can't capture a recording or screenshot (no browser tooling, no display, no fixture data), say so plainly and give the manual repro steps a human would follow — a described gap beats a faked artifact. Never describe a recording you didn't make.
- **Don't record secrets.** A capture picks up whatever is on screen — tokens, real user data, an open password manager, unrelated browser tabs. Record the app window, not the whole desktop, and check the artifact before you point the user at it.
- **Don't change code to make QA pass.** A failure here is a real signal — that's a bug for the debug skill, not something to patch around. Report it.
- **Local / dev only.** Never QA against production or with production credentials unless the user explicitly says so. Tear down any app or server you started.

## When NOT to use

- The change has no runtime surface — pure docs, comments, or a refactor with green tests. There's nothing to observe; don't force it.
- The user wants tests *written* — use **`{{REPO}}-test`**. QA runs and observes; it doesn't author test code.
- The user wants a bug *fixed* — use **`{{REPO}}-debug`**, then come back here to capture the fix working.
