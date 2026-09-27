---
name: httpx-new-worktree
description: Use when the user wants a new git worktree created for a task. Picks a kebab-case branch name with a fix/feat/chore/docs/refactor prefix, runs `git worktree add` from the configured base branch, and reports the new path. Also known as `klaussy-new-worktree`.
---

Create a new git worktree for the task the user described.

**Resolve the base first, by running the command.** Every range below is against `<base>`. Run `klaussy base --explain` before any range and reuse its answer; if the `klaussy` command isn't found, try `python3 -m klaussy base --explain` (`python -m klaussy` on Windows), then `git symbolic-ref --short refs/remotes/origin/HEAD` without its `origin/` prefix, and `master` if that's empty too. **Don't work the base out by eye.** Picking the obvious branch gets the same answer most of the time and misses the case that matters: the command also reports branches `HEAD` may have been cut from, and a branch stacked on another one gets a range covering commits your change never added. If it names any, say so and ask which base to use rather than picking. Either way, state the base you used, and that you checked.

1. Read CLAUDE.md to understand the project structure and branching conventions.
2. Create a short, descriptive branch name based on the task (e.g. `fix/login-redirect`, `feat/add-search`).
3. Take the current repository's folder name (you already know the working directory — don't compute it with a shell substitution like `$(basename $PWD)`, which isn't portable to Windows shells), and derive a directory slug from the branch name by replacing every `/` with `-` (`fix/login-redirect` → `fix-login-redirect`). Then run `git worktree add ../<repo-folder>-<dir-slug> -b <branch-name> <base>` to create the worktree from the resolved base (the trailing start-point keeps the new branch from inheriting whatever branch the user is currently checked out on). The branch keeps its slash; only the directory is flattened, because a slash in the path would nest the worktree inside a `<repo-folder>-fix/` directory instead of creating a sibling of the repo.
4. Confirm the worktree was created successfully with `git worktree list`.
5. Tell the user the full path to the new worktree so they can open it.

Rules:
- Always branch from `<base>` unless told otherwise. It is a start point, not a mention: cutting from a stale branch puts the new one on the wrong commit, and every range measured against it is wrong too.
- Use lowercase kebab-case for branch names.
- Prefix with `fix/`, `feat/`, `chore/`, `docs/`, or `refactor/` as appropriate.
- Do not start work in the worktree — just create it and report the path.

## When NOT to use

- The user just wants a new branch in the current working tree (`git checkout -b`) — worktrees are for parallel checkouts, not branch creation alone.
- A worktree for the same branch already exists — surface the existing path; don't create a duplicate.
- The user is on a non-worktree-friendly hosting setup (some submodule-heavy repos break with worktrees) — flag the risk before creating.
