---
name: httpx-run
description: Use when the user wants to run, start, or launch this project's app — to watch a change work end-to-end, reproduce behavior in the real app, or smoke-test locally. Finds the run command from CLAUDE.md and drives the app; it does not write features or fix bugs.
---

Run this project's app and drive it far enough to observe the behavior the user cares about. Don't just start it and call it done — exercise the actual flow.

## Steps

1. **Find the run command in CLAUDE.md.** Read CLAUDE.md — its **Commands** section is the source of truth for how this project installs, builds, and runs. Look for entries labeled run / start / serve / dev, a CLI entrypoint, or a server command (this project may expose more than one, e.g. a CLI *and* a server — pick the one that matches what the user asked for; if it's ambiguous, ask).
2. **Read any `.claude/rules/*.md`** whose `paths:` glob covers the code you're about to exercise — it may note required env vars, ports, or setup the command alone doesn't reveal.
3. **Fall back to the stack** only if CLAUDE.md names no run command (see the defaults below).
4. **Prepare the environment.** Install/build first *only if needed* (a fresh checkout, or the run command errors on missing deps) — e.g. the editable install or `npm install` from CLAUDE.md. If the app needs an env var, config file, or secret that isn't present, STOP and ask rather than inventing a value — a guessed secret produces a misleading failure.
5. **Run it, matched to the app's shape:**
   - **One-shot (CLI, script, build):** invoke it directly. Start with a cheap sanity call (`--help` / `--version`) to confirm it launches, then run a *representative real command* — the one that exercises the change or the behavior in question.
   - **Long-running (web server, watcher, MCP/daemon):** start it in the background, wait for its ready signal (a "listening on…" line, a health endpoint), then drive it from a second command — hit the endpoint, send a request, run the client. Tear it down when you're done; don't leave a stray process running.
6. **Observe and report.** Capture the actual output — the CLI result, the HTTP response, the rendered page, the log line. State plainly what you saw and whether it matches the expected behavior. If it failed, show the real error; don't paper over it.

## Stack defaults (if CLAUDE.md names no run command)

- **Python CLI**: the entrypoint under `[project.scripts]` in `pyproject.toml` (e.g. `mytool --help`), or `python -m <package>`.
- **Python web**: `uvicorn <module>:app --reload` (FastAPI/Starlette), `flask run` (Flask), `python manage.py runserver` (Django).
- **Node / TypeScript**: check `package.json` `scripts` for `dev` / `start` / `serve` — run `npm run dev` (or the pnpm/yarn/bun equivalent the repo uses).
- **Go**: `go run ./...`, or `go run ./cmd/<name>` when there are multiple entrypoints.
- **Rust**: `cargo run` (add `-- <args>` to pass CLI arguments).

If none of these fit and CLAUDE.md is silent, report that you can't determine how to launch the app and ask the user for the command — don't guess and run something destructive.

## Rules

- Do NOT change code to make the app run — if it's broken, that's a bug for the debug skill, not something to patch around here.
- Prefer the project's documented command over a hand-rolled one; the maintainers encoded setup and flags there for a reason.
- Never run with production credentials or against a production service. Local/dev only unless the user explicitly says otherwise.
- For a long-running process, always background it and confirm readiness before driving it — a foreground blocking start with no follow-up proves nothing.

## When NOT to use

- The user wants a change *implemented* or a bug *fixed* — use implement or debug; come back here to verify it runs.
- The change has no runtime surface to drive (docs, comments, pure refactor with green tests) — there's nothing to observe by launching the app.
- The user wants automated tests run, not the live app — use the test skill.
