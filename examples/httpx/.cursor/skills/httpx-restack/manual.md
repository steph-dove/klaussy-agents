# Restack by hand

Use this when the `klaussy` CLI isn't available. It's the same procedure `klaussy restack` runs, one git command at a time. Everything in the restack SKILL.md's Rules and forge sections still applies.

## Phase 1: Map the stack (git only)

Run `git fetch --all --prune` first so every comparison is against current refs.

1. **Read any recorded parents.** `git config --get-regexp '^branch\..*\.klaussyparent$'` returns mappings this skill stored on a previous run. Trust them, but verify each parent still exists as a branch.
2. **Derive the rest from ancestry.** Take the local branches ahead of the base: for each, `git rev-list --count origin/master..<branch>` must be greater than 0. Then for every ordered pair, `git merge-base --is-ancestor <a> <b>` (exit 0 means `a` is an ancestor of `b`). A branch's parent is its **nearest** ancestor in that set, the one with the highest `git rev-list --count origin/master..<ancestor>`. A branch with no branch ancestor sits directly on `master`.
   Ancestry misses a parent that was amended or rebased after the child branched: the parent's new tip is no longer an ancestor. `git merge-base --fork-point <parent> <child>` searches the parent's reflog for the commit the child grew from; use it to find such a parent, and use its output (not the parent's current tip) as that child's `--onto` boundary in Phase 3.
3. **Handle the ambiguous cases explicitly.** Two branches pointing at the same commit are ancestors of each other, that's an alias, not a stack, so ask which is which. A branch with two independent children is a fork in the stack, rebase each child separately and say so.
4. **Optionally cross-check against the forge** (see the forge commands in the restack SKILL.md) to attach PR/MR numbers and confirm the chain. This is enrichment, not the source of truth. If the forge disagrees with ancestry, the ancestry is what git will rebase, so surface the mismatch rather than silently picking one.
5. **Print the stack** as `master → branch-a → branch-b → branch-c` and confirm it with the user before rewriting anything. A wrong parent silently drops or duplicates commits.
6. **Record the confirmed mapping** so later runs are deterministic and forge-free: `git config branch.<child>.klaussyParent <parent>`.
7. **Check ownership.** `git log <parent>..<branch> --format='%an'` on each branch. If commits from another author are in the stack, say so and get explicit confirmation before force-pushing over their work.

## Phase 2: Build the safety net

1. **Require a clean tree.** `git status --porcelain` must be empty. If it isn't, stop and let the user commit or stash; a rebase over a dirty tree loses work.
2. **Record the pre-rebase tip of every branch:** `git rev-parse <branch>` for each. Keep this list, it's both the undo path (`git reset --hard <sha>`) and the input to the `--onto` commands below.
3. **Detect a bottom branch that already landed**, with git rather than a PR state field:
   - `git merge-base --is-ancestor <branch> origin/master` exits 0 → merged with history preserved.
   - Squash and rebase merges rewrite the SHAs, so ancestry misses them. Compare trees instead: `git merge-tree --write-tree origin/master <branch>` (git 2.38+) printing the same oid as `git rev-parse origin/master^{tree}` means the branch's content is already in the base.
   - The remote branch disappearing after `fetch --prune` corroborates it, since most forges delete on merge. Treat it as a hint, not proof.

## Phase 3: Rebase bottom-up

Work one branch at a time, in stack order. Two ways to do it, pick per repo:

**Preferred, git 2.38+ with a linear local chain:** check out the topmost branch and run `git rebase --update-refs origin/master`. Every intermediate branch ref moves with the replayed commits in a single pass. Verify each ref landed where expected before pushing.

**Explicit, always correct:** for each branch, rebase it off its parent's *old* tip onto its parent's *new* tip, using the SHAs from Phase 2:

```
git rebase --onto origin/master <old-parent-tip-sha> <bottom-branch>
git rebase --onto <bottom-branch> <old-bottom-tip-sha> <next-branch>
```

The `--onto` form is what keeps a child from replaying its parent's commits a second time. A bare `git rebase <parent>` after the parent was rewritten will do exactly that.

If the bottom branch already landed (Phase 2), `--onto origin/master <landed-branch-old-tip>` on the first surviving child drops those commits cleanly.

Do not use `-i`, and do not squash, reword, or reorder while restacking. A restack moves commits; changing them at the same time makes the diff impossible to review.

## Phase 4: Conflicts

Conflicts are expected mid-stack and are not a reason to abort the whole run.

1. Show the user the conflicting files and both sides of the hunk.
2. Resolve by understanding the change, not by taking a side wholesale. Never reach for `--ours` / `--theirs` to make it go away.
3. `git add` the resolution, `git rebase --continue`, and keep going.
4. If a conflict is genuinely ambiguous, `git rebase --abort`, restore the branch from its recorded SHA, and hand it back to the user with the specifics. Leaving the stack half-rebased is worse than stopping.

## Phase 5: Push

1. **Force-push bottom-up**, one branch per command: `git push --force-with-lease --force-if-includes origin <branch>`. The lease is what stops you clobbering a teammate's push; never fall back to a bare `--force` when the lease is refused, investigate why instead.
2. **Never force-push `master`.**
3. If a PR/MR needs its base retargeted (the parent changed or landed), do that *before* the push where the forge allows it, so the request doesn't briefly show its parent's commits as its own.

## Phase 6: Retarget the review requests

Follow the retarget step in the restack SKILL.md.

## Phase 7: Verify (git only)

1. For each pair, `git log --oneline <parent>..<child>` must show only that branch's own commits. Anything extra means a wrong `--onto`.
2. `git range-diff <old-tip>...<new-tip>` per branch confirms the rebase moved the commits without changing them. This is the check that catches a bad conflict resolution, and it needs no forge.
3. Report the stack's new shape, the old SHAs for recovery, and anything left for the user to retarget by hand. Say plainly that only the branches CI re-runs are verified, a clean rebase is not a passing test.
