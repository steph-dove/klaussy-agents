---
name: klaussy-update
description: Use when the user wants to refresh klaussy-generated boilerplate (per-agent conventions, skills, settings, hooks) across every scaffolded agent after upgrading klaussy itself. Re-runs the scaffold against the latest templates so this repo picks up new skills, prompt revisions, and convention rules.
argument-hint: "[--skip-enrich]"
allowed-tools: Read Bash(pipx *) Bash(klaussy *) Bash(pip *) Bash(git *)
---

# Klaussy update

Refresh this repository's klaussy-generated boilerplate to match the latest klaussy version, for every agent klaussy previously scaffolded (Claude Code, Gemini CLI, Cursor, Codex, GitHub Copilot, Google Antigravity, Cline, Aider).

## Steps

1. **Upgrade klaussy first.** Run `pipx upgrade klaussy` (or `pip install --user --upgrade klaussy` if klaussy wasn't installed via pipx). Verify the new version with `klaussy --version`. Note the version for the report at the end.

2. **Read the existing version marker.** `cat .claude/skills/.klaussy-version` captures the version that last generated the skills. If the new klaussy version is the same as the marker, klaussy will skip — surface that to the user and confirm they want to proceed anyway (rare; usually only useful if you've also bumped `klaussy-repo-conventions` and want to re-run the path-scoped CLAUDE.md emission).

3. **Detect the base branch** the same way `klaussy-init` does (`git branch --list dev develop main master | head -1`).

4. **Run `klaussy init --force`.** The `--force` flag overrides the version-skip check and rewrites all generated files with the new templates:
   ```
   klaussy init --force --base-branch <detected> $ARGUMENTS
   ```

5. **Diff the result.** Run `git diff` over the generated files for every scaffolded agent — Claude (`CLAUDE.md`, `.claude/`) plus any of `GEMINI.md`/`.gemini/`, `AGENTS.md` (Codex/Antigravity), `.cursor/`, `.github/copilot-instructions.md`/`.github/skills/`, `.clinerules/`, `CONVENTIONS.md` (Aider) that exist — and summarize the substantive changes for the user:
   - New skills added or removed
   - Prompt body changes in `<repo>-plan` / `<repo>-review` / etc.
   - New / changed rule files (e.g. under `.claude/rules/`)
   - Settings or hook changes
   This is the user's chance to review before committing the refresh.

6. **Report.** Tell the user the old marker version → new version, what materially changed in the generated content, and remind them to commit.

## When NOT to use

- The repo isn't klaussified yet — use the `klaussy-init` skill instead (running `klaussy init --force` on a clean repo works but the skill auto-detect is cleaner).
- The user only wants to update one specific surface (just skills, just hooks, just settings) — they can run `klaussy skills`, `klaussy hooks`, or `klaussy settings` directly without `init --force`.
- The user pinned an older klaussy version intentionally and doesn't want to upgrade — skip step 1 and re-run `klaussy init --force` against the existing version, but flag that this is unusual.
