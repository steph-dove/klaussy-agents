---
name: {{REPO}}-fix
description: Use when the user wants lint, format, and type errors fixed in the current changes. Reads CLAUDE.md for the repo's lint/format/type-check commands, runs each, and fixes only style/format/type issues — no behavior changes.
allowed-tools: Read Grep Glob Bash Edit
---

Fix all lint, format, and type errors in the current changes.

## Steps

1. **Read CLAUDE.md** to find the project's lint, format, and type-check commands. If they're missing, fall back to the stack defaults below.
2. **Read any `.claude/rules/*.md`** whose `paths:` glob matches the files you're about to touch — they may carry style/typing rules the linter doesn't enforce.
3. **Scope to this branch's change.** Build the changed-file list — the union of:
   - `git diff --name-only {{BASE_BRANCH}}...HEAD` (work committed on this branch)
   - `git diff --name-only` (unstaged) and `git diff --name-only --cached` (staged)

   Pass these paths to every command below so the tools judge only what this branch changed — never the whole repo. Pre-existing violations in untouched files are not yours to fix here. If the list is empty, there's nothing to fix; say so and stop. (If `{{BASE_BRANCH}}...HEAD` errors because the base branch isn't present locally, fall back to the uncommitted diff alone.)
4. **Run each command in this order, scoped to the changed files** (apply each pass before running the next, so fixes from one don't fight the next):
   1. **Format** first (it normalizes whitespace and quoting that lint rules might complain about).
   2. **Lint** next (it picks up real style/safety issues on top of formatted code).
   3. **Type-check** last (type errors don't move under format/lint, but the line numbers will). If the type-checker needs whole-project context to resolve imports, run it normally but only fix errors that land in the changed files.
5. **Fix all reported issues.** When format and lint disagree on a specific construct, lint wins (formatters auto-resolve; lint encodes intent).
6. **Re-run all three** (still scoped to the changed files) to verify they're clean.

## Stack defaults (if CLAUDE.md doesn't specify commands)

Append the changed files to each command (e.g. `ruff check <files>`) so it stays scoped to the branch's change.

- **Python**: `ruff format`, `ruff check`, `mypy` (or `pyright`)
- **TypeScript / JavaScript**: `prettier --write`, `eslint --fix`, `tsc --noEmit` (`tsc` checks the whole project — read only the changed files' errors)
- **Go**: `gofmt -w` / `goimports -w`, `go vet`, `staticcheck`
- **Rust**: `cargo fmt`, `cargo clippy --fix`, `cargo check` (cargo works per-crate — limit fixes to the changed files)

If none of these are configured (no `pyproject.toml`/`package.json`/`go.mod`/`Cargo.toml` entry, no devDependency installed), report that the repo has no configured lint/format/type-check toolchain and stop — don't pick one and force it on the project.

## Rules

- Do NOT change logic or behavior. Only fix style, formatting, and type issues.
- If a type error reveals a real bug (e.g. a function call missing a required argument), STOP. Report it as a bug for the debug skill to take, don't paper over it with a cast or `Any`.
- If lint flags an existing violation in unchanged code (not from your diff), leave it alone unless explicitly asked to fix repo-wide.
- Remove commented-out code in the lines you're touching (the pre-commit guard blocks it). Don't add narrating comments while fixing — keep only short "why" comments.

## When NOT to use

- The user wants behavior changes, refactors, or bug fixes — those are different skills.
- The repo has no linter/formatter/type-checker — there's nothing to run.
- The errors are runtime errors or test failures, not lint/format/type errors — use debug instead.
