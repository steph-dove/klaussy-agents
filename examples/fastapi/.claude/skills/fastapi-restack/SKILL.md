---
name: fastapi-restack
description: Use when the user has a stack of dependent branches or PRs that needs rebasing — the base branch moved, the bottom branch merged, or a mid-stack branch was amended. Derives the parent/child chain from git ancestry, rebases each branch onto its new parent, and force-pushes with a lease. Works with plain git; uses a forge CLI only to retarget PR/MR bases when one is available. Also known as `klaussy-restack`.
allowed-tools: Read Grep Bash(git *) Bash(gh *) Bash(glab *)
---

Rebase a stack of dependent branches so each one sits on top of its parent again, then push the stack. Everything load-bearing here is plain git: the topology comes from commit ancestry, not from a hosting provider. A forge CLI is used only for the last mile (retargeting a PR/MR base), and its absence never blocks the rebase.

## Phase 1: Map the stack (git only)

Run `git fetch --all --prune` first so every comparison is against current refs.

1. **Read any recorded parents.** `git config --get-regexp '^branch\..*\.klaussyparent$'` returns mappings this skill stored on a previous run. Trust them, but verify each parent still exists as a branch.
2. **Derive the rest from ancestry.** Take the local branches ahead of the base: for each, `git rev-list --count origin/master..<branch>` must be greater than 0. Then for every ordered pair, `git merge-base --is-ancestor <a> <b>` (exit 0 means `a` is an ancestor of `b`). A branch's parent is its **nearest** ancestor in that set, the one with the highest `git rev-list --count origin/master..<ancestor>`. A branch with no branch ancestor sits directly on `master`.
3. **Handle the ambiguous cases explicitly.** Two branches pointing at the same commit are ancestors of each other, that's an alias, not a stack, so ask which is which. A branch with two independent children is a fork in the stack, rebase each child separately and say so.
4. **Optionally cross-check against the forge** (see the adapter below) to attach PR/MR numbers and confirm the chain. This is enrichment, not the source of truth. If the forge disagrees with ancestry, the ancestry is what git will rebase, so surface the mismatch rather than silently picking one.
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

## Phase 6: Retarget the review requests (optional)

Rebasing is done and pushed by this point. This phase only fixes the "base branch" field on open pull/merge requests whose parent changed or landed.

### Forge commands (GitHub)

`origin` points at GitHub, so the `gh` CLI is the adapter. Confirm a flag with `gh <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `gh issue view <n> --comments` |
| Open a request | `gh pr create --base <branch> --title <title> --body-file <file>` |
| Request status | `gh pr view <n> --json state,mergeable,reviewDecision,baseRefName` |
| CI status | `gh pr checks <n>`, then `gh run view <run-id> --log-failed` on a failure |
| Read review comments | `gh api repos/{owner}/{repo}/pulls/<n>/comments` |
| Reply in a thread | `gh api --method POST repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body=<text>` |
| Resolve a thread | two steps, see below — REST can't do it |
| Retarget a request | `gh pr edit <n> --base <branch>` |

`{owner}/{repo}` are placeholders `gh` fills from the current repo, leave them literal.

**Resolving needs GraphQL, and the id it wants is not the comment id.** The REST comment objects don't carry it, so read the thread ids first, then resolve one:

```
gh api graphql -f query='{ repository(owner: "<owner>", name: "<repo>") {
  pullRequest(number: <n>) { reviewThreads(first: 50) { nodes {
    id isResolved comments(first: 1) { nodes { databaseId body } } } } } } }'

gh api graphql -f query='mutation($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }' -F id=<thread-node-id>
```

Match a thread to the comment you replied to through `comments.nodes[].databaseId`, which is the REST comment id. `threadId` is the only required input.

A reply must name the thread it answers. The `replies` endpoint above takes only `body`; the alternative is `POST .../pulls/<n>/comments` with `-F in_reply_to=<comment-id>` (an integer, hence `-F`). Posting to `comments` without `in_reply_to` opens a new top-level review comment rather than replying.

**GitHub has native stacks**, driven by the `gh-stack` extension. `gh extension list` says whether it's installed. If it isn't, **offer to install it** — `gh extension install github/gh-stack`, one command, no repo changes — and say what it buys before asking: a stack map and layer navigation on every request page, plus cascading rebase when the base moves. Ask rather than installing unprompted, since it touches the user's `gh` setup and not this repo, but do ask; silently settling for bare chained bases hands back a worse result than the one command would have. Declining is a fine answer and the fallback below still works.

The extension is in public preview, so check `gh stack <command> --help` before relying on a flag.

| Need | Command |
| :--- | :--- |
| Link requests that already exist into a stack | `gh stack link --base <branch> <branch-or-pr> <branch-or-pr> ...` |
| Track a carved chain locally | `gh stack init --base <branch> <branch> ...` |
| Push the tracked chain and open or update its requests | `gh stack submit` |
| See the stack | `gh stack view` |
| Cascading rebase after the base moved | `gh stack rebase` |
| Fetch, rebase, push, and sync in one pass | `gh stack sync` |

Arguments run bottom-up, nearest the base first. Two constraints decide whether a stack is available at all: **every branch must live in this repo** (cross-fork stacks aren't supported), and the extension has to be installed.

`link` and `init` are two different entry points and the difference shows up later. `link` stacks requests that already exist and leaves nothing behind locally, so a later `gh stack rebase` needs `gh stack checkout <stack-number>` first to pick the stack back up. `init` registers the branches locally up front and `submit` then opens the requests itself, which means the bodies are its own — write them with `gh pr edit <n> --body-file` afterwards if they have to say something specific.

Without it, chained `--base` targets still give reviewers a per-layer diff, and GitHub often offers to convert an eligible chain into a stack — a banner on the request, or "Add to stack" behind the stack icon. Say which route you took.


**A missing, unauthenticated, or nonexistent CLI is not a failure here.** The git work is already complete. Print what's left: each branch, its new parent, the request URL if you can construct one from the remote, and the one field to change. Never ask the user to install a hosting CLI to finish a rebase.

## Phase 7: Verify (git only)

1. For each pair, `git log --oneline <parent>..<child>` must show only that branch's own commits. Anything extra means a wrong `--onto`.
2. `git range-diff <old-tip>...<new-tip>` per branch confirms the rebase moved the commits without changing them. This is the check that catches a bad conflict resolution, and it needs no forge.
3. Report the stack's new shape, the old SHAs for recovery, and anything left for the user to retarget by hand. Say plainly that only the branches CI re-runs are verified, a clean rebase is not a passing test.

## Rules

- Git is the source of truth for topology. A forge CLI may enrich or confirm; it is never required, and it never gates the rebase.
- Confirm the parent/child mapping with the user before the first rewrite. Everything after that depends on it.
- One branch per push command, in order. Bulk-pushing a stack hides which branch failed.
- Never delete branches as part of a restack, even ones that already landed.
- If the repo uses a stack tool (Graphite, git-town, spr, ghstack), use its own restack command instead so its metadata stays consistent. Say which tool you found. The same goes for a host-native stack — the forge commands in Phase 6 say whether this host has one and which command cascades the rebase across it; driving that by hand leaves the host's own record of the stack stale.

## When NOT to use

- A single branch based on `master` is behind — that's a plain `git rebase origin/master`, no stack machinery needed.
- The user wants to land the stack (merge each request in order) — different task, different risks.
- The branches live in a fork or you lack push rights — the rebase will succeed locally and the push will fail; check first.
- The stack is shared and teammates have unpushed work on it — coordinate before rewriting, force-with-lease can't protect what it hasn't seen.
