---
name: {{REPO}}-new-worktree
description: Use when the user wants a new git worktree created for a task. Picks a kebab-case branch name with a fix/feat/chore/docs/refactor prefix, runs `git worktree add` from the configured base branch, and reports the new path.
allowed-tools: Read Bash(git worktree *) Bash(git branch *)
disable-model-invocation: true
---

Create a new git worktree for the task the user described.

1. Read CLAUDE.md to understand the project structure and branching conventions.
2. Create a short, descriptive branch name based on the task (e.g. `fix/login-redirect`, `feat/add-search`).
3. Run `git worktree add ../$(basename $PWD)-<branch-name> -b <branch-name> {{BASE_BRANCH}}` to create the worktree from the configured base branch (the trailing start-point keeps the new branch from inheriting whatever branch the user is currently checked out on).
4. Confirm the worktree was created successfully with `git worktree list`.
5. Tell the user the full path to the new worktree so they can open it.

Rules:
- Always branch from {{BASE_BRANCH}} unless told otherwise.
- Use lowercase kebab-case for branch names.
- Prefix with `fix/`, `feat/`, `chore/`, `docs/`, or `refactor/` as appropriate.
- Do not start work in the worktree — just create it and report the path.

## When NOT to use

- The user just wants a new branch in the current working tree (`git checkout -b`) — worktrees are for parallel checkouts, not branch creation alone.
- A worktree for the same branch already exists — surface the existing path; don't create a duplicate.
- The user is on a non-worktree-friendly hosting setup (some submodule-heavy repos break with worktrees) — flag the risk before creating.
