---
name: klausify-init
description: Use when the user wants to make this repository Claude Code-ready. Scaffolds CLAUDE.md (path-scoped via conventions-cli), repo-namespaced .claude/skills/<repo>-<skill>/, settings.json, hooks, and a PR template — and runs once per repo.
argument-hint: "[--force] [--skip-enrich] [--base-branch <branch>]"
allowed-tools: Read Bash(pipx *) Bash(klausify *) Bash(pip *) Bash(git *)
---

# Klausify init

Scaffold Claude Code boilerplate for the user's project by running klausify.

## Steps

1. **Confirm klausify is available.** Run `klausify --version`. If the command isn't found, install with `pipx install klausify` (preferred) or `pip install --user klausify`. Re-verify with `klausify --version` afterward.

2. **Detect the base branch.** Klausify will prompt interactively if not given, which blocks the agent. Pre-detect via `git branch --list dev develop main master | head -1` and pass `--base-branch <detected>`. If none of those exist, fall back to whatever `git symbolic-ref refs/remotes/origin/HEAD` returns, or `main`.

3. **Run klausify init.** Pass through `$ARGUMENTS` if the user supplied any (e.g. `--force`, `--skip-enrich`):
   ```
   klausify init --base-branch <detected> $ARGUMENTS
   ```
   If `.claude/skills/` or `./CLAUDE.md` already exists, ask the user whether to pass `--force` rather than assuming. The migration in `klausify init` removes legacy `.claude/commands/*.md` files only if it owns them (via the `.klausify-version` marker) — user-authored commands are left alone.

   **Agent targets.** By default klausify scaffolds **all** supported agents — Claude Code, Gemini CLI, Cursor, Codex, and GitHub Copilot — from the same conventions. Each gets the bundled skills in its own native `SKILL.md` directory (`.claude/skills/`, `.gemini/skills/`, `.cursor/skills/`, `.agents/skills/` for Codex, `.github/skills/` for Copilot), plus its native conventions file (`CLAUDE.md` / `GEMINI.md` / `AGENTS.md` / `.github/copilot-instructions.md` / `.cursor/rules/`) and permissions. To narrow to specific agents, pass `--agents claude,gemini` (any subset). If the user only uses Claude, suggest `--agents claude`.

4. **Verify output.** Confirm these landed:
   - `./CLAUDE.md` at the repo root (with project-wide content)
   - `.claude/rules/<glob-stem>.md` for each path-scoped rule bucket conventions-cli detected (zero or more files; some repos won't have any)
   - `.claude/skills/<repo>-<skill>/SKILL.md` for 11 skills (review, plan, debug, implement, refactor, test, fix, pr, commit, explain, new-worktree)
   - `.claude/settings.json`
   - `.github/PULL_REQUEST_TEMPLATE.md` (only if the repo didn't already have one)
   - `.gitignore` updated with klausify output exclusions

5. **Report.** Tell the user which skills were created (point at `<repo>-plan` and `<repo>-review` as the high-leverage ones), summarize what's in `CLAUDE.md` and any `.claude/rules/*.md` files, and suggest reviewing them before committing.

## When NOT to use

- The repo is already klausified at the same klausify version — `klausify init` will be a near-no-op; suggest the `klausify-update` skill instead if the user actually wants to refresh.
- The user wants a different scaffold tool (Cursor's setup, cookiecutter, an org-internal generator) — klausify is Claude Code-specific.
- The repo is empty or has no committed code yet — klausify infers conventions from the existing code; an empty repo gets generic boilerplate that the user may want to defer until there's something to detect from.
