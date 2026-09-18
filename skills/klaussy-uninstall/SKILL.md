---
name: klaussy-uninstall
description: Use when the user wants klaussy's scaffolding out of a repository — removing the generated skills, hooks, settings, and ignore files that `klaussy init` wrote, and optionally the package itself. Previews everything before deleting, keeps hand-edited conventions docs by default, and never touches files klaussy doesn't own.
argument-hint: "[--all] [--dry-run]"
allowed-tools: Read Bash(klaussy *) Bash(pipx *) Bash(pip *) Bash(git *)
---

# Klaussy uninstall

Remove what `klaussy init` put into this repository. The work is done by
`klaussy uninstall`, which knows which files klaussy owns; do not delete paths
by hand, because klaussy *merges* into `.gitignore` and each agent's settings
rather than owning them, and a manual `rm` takes the user's own entries too.

## Steps

1. **Check the tree is clean.** Run `git status --short`. If there are
   uncommitted changes, say so and ask whether to continue — this deletes files,
   and a clean tree is what makes it reversible with `git checkout`.

2. **Preview first, always.** Run:
   ```
   klaussy uninstall --dry-run
   ```
   It prints every path it would remove with the reason, every shared file it
   would edit, and everything it is deliberately keeping. Show the user the
   summary — counts plus anything under "keep" — rather than pasting hundreds of
   lines.

3. **Confirm scope.** Conventions docs (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`,
   `CONVENTIONS.md`) are kept by default, because people hand-edit them and
   klaussy can't tell their prose from its own. Ask whether the user wants those
   gone too; if so, add `--all`. Pass `$ARGUMENTS` through if they supplied any.

4. **Run it.**
   ```
   klaussy uninstall --yes
   ```
   Add `--all` only if step 3 established that. The command reports what it
   removed and what it left.

5. **Review the diff.** `git status --short` and `git diff` over the shared
   files it edited (`.gitignore`, `.claude/settings.json`, and any other agent
   settings). Confirm the user's own entries survived — that is the thing most
   worth checking, and it is why the command edits those files instead of
   deleting them.

6. **Offer to remove the package.** The repo is clean at this point but the CLI
   is still installed. Ask before running anything:
   `pipx uninstall klaussy-agents`, or `pip uninstall klaussy-agents` if it went
   in through pip. Leave it alone if the user works in other klaussified repos.

7. **Report.** Say what was removed, what was kept and why, and whether the
   package is still installed.

## What it deliberately leaves

Anything it cannot prove is klaussy's. A `.cursorignore` the user wrote keeps
its entries and only loses klaussy's marked block; a settings file with custom
hooks keeps them; a config carrying a key klaussy never writes is left whole.
These show up under "keep" in the preview, so surface them rather than trying to
finish the job by hand.

## When NOT to use

- The user wants to *refresh* the scaffolding rather than remove it — that's the
  `klaussy-update` skill, or `klaussy init --force`.
- The user wants only one agent's files gone. Uninstall is all-or-nothing; point
  them at deleting that agent's directory and re-running `klaussy init --agents`
  with the set they want to keep.
- Only the package should go, not the repo files — that's a plain
  `pipx uninstall klaussy-agents`, no skill needed.
