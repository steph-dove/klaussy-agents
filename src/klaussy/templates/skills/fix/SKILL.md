---
name: {{REPO}}-fix
description: Use when the user wants lint, format, and type errors fixed in the current changes. Reads CLAUDE.md for the repo's lint/format/type-check commands, runs each, and fixes only style/format/type issues — no behavior changes.
allowed-tools: Read Grep Glob Bash Edit
---

Fix all lint, format, and type errors in the current changes.

## Steps

1. **Read CLAUDE.md** to find the project's lint, format, and type-check commands. If they're missing, fall back to the stack defaults below.
2. **Read any `.claude/rules/*.md`** whose `paths:` glob matches the files you're about to touch — they may carry style/typing rules the linter doesn't enforce.
3. **Run each command in this order** (apply each pass before running the next, so fixes from one don't fight the next):
   1. **Format** first (it normalizes whitespace and quoting that lint rules might complain about).
   2. **Lint** next (it picks up real style/safety issues on top of formatted code).
   3. **Type-check** last (type errors don't move under format/lint, but the line numbers will).
4. **Fix all reported issues.** When format and lint disagree on a specific construct, lint wins (formatters auto-resolve; lint encodes intent).
5. **Re-run all three** to verify the working tree is clean.

## Stack defaults (if CLAUDE.md doesn't specify commands)

- **Python**: `ruff format`, `ruff check`, `mypy` (or `pyright`)
- **TypeScript / JavaScript**: `prettier --write`, `eslint --fix`, `tsc --noEmit`
- **Go**: `gofmt -w` / `goimports -w`, `go vet`, `staticcheck`
- **Rust**: `cargo fmt`, `cargo clippy --fix`, `cargo check`

If none of these are configured (no `pyproject.toml`/`package.json`/`go.mod`/`Cargo.toml` entry, no devDependency installed), report that the repo has no configured lint/format/type-check toolchain and stop — don't pick one and force it on the project.

## Rules

- Do NOT change logic or behavior. Only fix style, formatting, and type issues.
- If a type error reveals a real bug (e.g. a function call missing a required argument), STOP. Report it as a bug for the debug skill to take, don't paper over it with a cast or `Any`.
- If lint flags an existing violation in unchanged code (not from your diff), leave it alone unless explicitly asked to fix repo-wide.

## When NOT to use

- The user wants behavior changes, refactors, or bug fixes — those are different skills.
- The repo has no linter/formatter/type-checker — there's nothing to run.
- The errors are runtime errors or test failures, not lint/format/type errors — use debug instead.
