---
name: httpx-grant-permissions
description: Use when the user is tired of approving the same routine dev work ("stop asking me yes", "allow the normal dev tools", "grant permissions"). Detects the repo's stack and writes a curated allow-list into the agent's own local permission file so the basics stop prompting — reading, editing and creating files, plus tests, lint, build, git, the package manager and the run command — while keeping secret files denied.
---

Grant the permissions a developer needs to work in this repo without a prompt on every routine command, while keeping sensitive files off-limits.

Permissions live in your agent's config file, not in memory or preferences — this skill edits that file. It does NOT loosen anything silently: propose the allow-list, show it, then write it.

## Where your allow-list lives

You're running **Cursor**. Write permissions to `.cursor/permissions.json` (plus secret globs in `.cursorignore`), using its `allow` / `deny` arrays. Prefer the local, git-ignored file so one developer's convenience list isn't committed onto the team; only write a shared, committed file if the user asks to apply it team-wide. The rule examples below use Claude Code's `Bash(...)` / `Edit(...)` form, translate them to your file's shape.

## Steps

1. **Find the repo's real commands.** Read CLAUDE.md and any rules files first. If there's no CLAUDE.md (common on third-party repos), fall back to `README.md`, `CONTRIBUTING.md`, `package.json` `scripts`, a `Makefile`/`justfile`/`Taskfile.yml`, and a `scripts/` directory. Capture test, lint, format, type-check, build, and especially the **run/dev/start** command — that's the one people forget to allow.
2. **Detect the stack and its runner** from marker files:
   - `pyproject.toml` / `setup.py` → `python`, `pytest`, `ruff`, `mypy`/`pyright`, `pip`, `uv`
   - `package.json` → `npm`, `npx`, `node`, `yarn`, `pnpm` (read its `scripts`)
   - `go.mod` → `go`; `Cargo.toml` → `cargo`; `Makefile` → `make`
   - `docker-compose.yml` / `Dockerfile` → `docker`, `docker compose`
   - **A `scripts/` directory or a Makefile is the entrypoint in many repos** (FastAPI runs `bash scripts/test.sh`; httpx runs `scripts/test`, `scripts/check`, `scripts/lint`). A `Bash(pytest *)` rule does NOT cover `scripts/test` — allow the runner itself (next step) or the tests still prompt.
3. **Read the current permission file(s)** so you merge instead of clobbering. Preserve every existing allow/deny entry and any hook config.
4. **Build the allow-list** (curated mode — the default):
   - **The file tools, bare:** `Read`, `Edit`, `Write`, `Grep`, `Glob`. These are table stakes — an agent that has to ask before reading a file or writing a new one is unusable for local dev, and they're the same baseline `klaussy settings` writes. A bare name (no parens) allows the tool for any path; the step-5 denies still win, so secrets stay blocked. Don't write `Write(**)` — see the `Edit`/`Write` rule below.
   - `Bash(git *)`
   - **Navigation/inspection builtins** that otherwise block compound commands (see the compound-command note): `Bash(cd *)`, `Bash(ls *)`, `Bash(pwd)`, `Bash(echo *)`, `Bash(mkdir *)`, `Bash(which *)`, `Bash(cat *)`, `Bash(head *)`, `Bash(tail *)`, `Bash(wc *)`, `Bash(find *)`, `Bash(grep *)`, `Bash(rg *)`, `Bash(sort *)`, `Bash(diff *)`
   - **Everyday file moves:** `Bash(cp *)`, `Bash(mv *)`, `Bash(touch *)`. `rm` is deliberately not here — deleting is the one routine command worth a prompt. Add it only on request.
   - one `Bash(<tool> *)` per stack command from step 2 (e.g. `Bash(pytest *)`, `Bash(npm *)`, `Bash(cargo *)`)
   - **the repo's runner** if it uses one: `Bash(bash scripts/*)`, `Bash(sh scripts/*)`, `Bash(./scripts/*)`, `Bash(scripts/*)`, `Bash(make *)`
   - **the run/dev command** as its own entry (e.g. `Bash(fastapi dev *)`, `Bash(uvicorn *)`, `Bash(npm run dev *)`, `Bash(docker compose *)`)
5. **Keep sensitive files denied.** Add to `deny` if absent (see the `Edit` vs `Write` rule below): `Read(**/.env)` + `Edit(**/.env)`, and the same pair for `**/.env.*`, `**/.envrc`, `**/credentials.json`, `**/.aws/credentials`, `**/.npmrc`, `**/*.pem`, `**/*.key`, `**/id_rsa`, `**/id_ed25519`. For agents with an ignore file (`.cursorignore`, `.geminiignore`), add the secret globs there too — those block Bash reads that per-tool deny rules miss (see safety note).
6. **Merge and write.** Union new entries into the existing arrays, drop exact duplicates, write valid JSON (or the agent's format). Report exactly what you added.
7. **Tell the user how to widen or narrow it** — that broad mode exists, and that removing an entry re-enables its prompt.

## Why `cd` and the builtins matter: compound commands

A Bash rule matches by prefix (`Bash(git *)` matches anything starting with `git `). But the agent splits a compound command on `&&`, `||`, `;`, and `|` and checks **each segment separately** — the line runs unprompted only if *every* segment matches.

So `cd services/api && npm run dev` prompts even when `Bash(npm run dev *)` is allowed, because the `cd services/api` segment isn't. That's the top reason a "fully allowed" toolchain still asks — run, test, and build commands are routinely prefixed with `cd`. Allowing `cd` plus the read builtins closes it. Match the syntax exactly: `Bash(cd *)` with a **space** before `*`, not a colon.

## What curated mode does and doesn't protect (the safe boundary)

Curated mode is a reasonable boundary for a **trusted local dev agent**, not a security sandbox. Be honest with the user about the line:

- **It does** stop routine prompts, block obviously-destructive arbitrary shell (no blanket `Bash(*)`), and prevent accidental *edits* to secret files via the Read/Edit/Write tools.
- **The file tools are unscoped.** Bare `Read`/`Edit`/`Write` allow any path the denies don't cover, not just paths inside the repo — an agent working in this repo can still write to your home directory. That's the normal trade for a local dev agent, and path-scoping every rule is what makes an allow-list unusable; but it's a trade, so say it rather than imply a repo sandbox. Same for `Bash(cp *)`/`Bash(mv *)`: they overwrite without asking.
- **It does not** sandbox execution. `Bash(python *)`, `Bash(pip *)`, `Bash(uv *)`, and `Bash(npx *)` all run arbitrary code (a language runtime executes anything; `pip install` runs a package's setup code). Only allow these for an agent you trust to run this repo's code — which is the normal case for local dev, but say it out loud.
- **Per-tool deny is not a wall against Bash.** A `deny` on `Read(**/.env)` only stops the *Read tool*; `Bash(cat *)` can still `cat .env`. So the secret-file denies protect Read/Edit, not Bash. If secrets in the repo are a real concern, either don't allow `Bash(cat *)`/`Bash(head *)` (read files with the Read tool, which honors deny) or add the secret globs to the agent's ignore file (`.cursorignore`/`.geminiignore`), which some agents enforce for Bash too. Don't claim the denies protect against Bash — they don't.
- **Deliberately excluded from the default builtins:** `source`/`.` (executes an arbitrary file), `env`/`printenv` (dumps secrets in the environment), `eval`, `xargs`. Add them only on request.

## Broad mode (only when the user asks)

For the fewest prompts, accepting the wider blast radius, replace the curated Bash entries with `Bash(*)`, and `Edit(**)` / `Read(**)`. Keep the step-5 denies (deny wins over allow), and keep the ignore-file globs, since `Bash(*)` makes the Bash-bypass above trivial. Say plainly that broad mode trusts the agent with arbitrary commands; never pick it by default.

## Cross-platform

Permission rule *strings* are OS-agnostic — the same `Bash(pytest *)` works on macOS, Linux, and Windows. Two things do differ:

- **Windows shells.** Claude Code and most agents run Bash through Git Bash or WSL, so the POSIX builtins above (`cd`, `ls`, `cat`) still apply. If the user drives commands through native `cmd`/PowerShell instead, `dir`/`type`/`Get-ChildItem` won't match POSIX rules — allow those variants for that user.
- **Run-command paths.** Write run/dev commands with forward slashes and no OS-specific absolute paths (`Bash(cd services/api *)`, not a `C:\...` path), so the same local file works across a mixed-OS team. That's also why the personal, git-ignored file is the right default target.

## The one rule that trips people up: `Edit(<path>)`, never `Write(<path>)`

Path-scoped rules are matched by the file-permission checker, and (in Claude Code) that checker **only understands `Edit(<path>)`** — an `Edit` rule covers every file-editing tool, Write included. A `Write(<path>)` path rule (allow OR deny) is silently ignored: it matches nothing, protects nothing, and produces a startup warning.

- Deny a file: `Edit(**/*.pem)`. Don't add a redundant `Write(**/*.pem)` — it only triggers the warning.
- Allow file edits broadly: `Edit(**)`. A bare `Write` (no parens) in `allow` is fine; `Write(**)` as a path rule is not.
- If the file already pairs `Edit(<path>)` + `Write(<path>)`, the `Write(<path>)` ones are dead weight — offer to strip them.

## When NOT to use

- The user wants to change *what* an agent does, not what it's allowed to do — that's a conventions/skill change.
- The user wants an automatic behavior on every tool call (block X, run Y after Z) — that's a hook, not a permission rule.
- A single one-off command needs approving — just approve it; don't rewrite the allow-list for one prompt.
- The user asks to allow something dangerous with no scope (`Bash(rm -rf *)`, dropping all denies) — surface the risk and confirm first.
- The agent is Aider (or any tool without a per-command allow-list) — there's nothing to grant; explain the gating it does have instead.
