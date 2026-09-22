---
name: httpx-worktree-cleanup
description: Use when the user wants stale or unused git worktrees cleaned up. Classifies every worktree as merged, abandoned, dirty, or in use, proposes which to remove, and on confirmation removes them with `git worktree remove` and prunes the leftovers. Never forces a removal and never touches uncommitted work. Also known as `klaussy-worktree-cleanup`.
allowed-tools: Read Bash(git *)
---

Remove the git worktrees nobody is using any more, without losing work.

## 1. Gather

1. Run `git fetch --prune` so remote branches deleted after a merge show as gone. Squash merges leave no ancestry behind, so a gone upstream is often the only sign a branch landed.
2. Resolve the base: `git symbolic-ref --short refs/remotes/origin/HEAD`, else `origin/master`. Use the branch the user names instead, if any.
3. Run `git worktree list --porcelain`. Skip the main worktree (the first entry) and the one you're running in.

## 2. Classify each remaining worktree

Collect these for each one. Every check is read-only, run with `git -C <path>`:

- **Dirty:** `status --porcelain` prints anything, untracked files included.
- **Unpushed:** `log --oneline @{u}..` is non-empty, or there's no upstream and `log --oneline <base>..HEAD` is non-empty.
- **Merged:** `merge-base --is-ancestor HEAD <base>` succeeds, or the upstream shows `[gone]` in `git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads`.
- **Last activity:** `log -1 --format=%cr`.
- **Locked or prunable:** the porcelain listing says so. A prunable entry's directory is already gone.

Then put each worktree in exactly one bucket:

| Bucket | Rule | Proposal |
| :--- | :--- | :--- |
| Prunable | Directory missing | Prune |
| Merged | Clean, nothing unpushed, merged or upstream gone | Remove |
| Abandoned | Clean, no commits beyond base, no activity for 14+ days | Remove, ask first |
| Keep | Dirty, unpushed commits, locked, or active in the last day | Keep, say which reason |

If `$KLAUSSY_SESSION_NOTES_DIR` is set, check its notes for the worktree's path or branch. Another agent may be working there, so a match moves the worktree to Keep.

## 3. Confirm

Show one table: path, branch, bucket, reason, last activity. List exactly what you'll remove and wait for the user to confirm, or to strike items from the list.

## 4. Remove

1. `git worktree remove <path>` for each confirmed entry. If git refuses, report why and move on. Do not retry with `--force`.
2. `git worktree prune` for the prunable entries and any leftover admin files.
3. Offer to delete each removed worktree's local branch with `git branch -d <branch>`. `-d` refuses a branch that isn't merged by ancestry, which is what happens after a squash merge. Use `-D` only for a branch whose upstream is gone, and only after the user confirms that branch by name.
4. Finish with `git worktree list` and report what was removed and what was kept, one line each.

## Rules

- Never pass `--force` to `git worktree remove`, and never remove a worktree with uncommitted or unpushed work. Losing that work can't be undone.
- Never remove the main worktree or the one you're running in.
- Removing a worktree deletes its directory, including ignored build output. Name that in the confirmation if a worktree holds a large ignored tree someone might want, such as a `.venv` or `node_modules`.

## When NOT to use

- The user wants a worktree created. Use the new-worktree skill.
- The user wants to throw away uncommitted work in a worktree. That's a deliberate discard, so have them confirm it and run it themselves.
