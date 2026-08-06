---
name: {{REPO}}-split-pr
description: Use when a change is too large to review in one pass and should ship as a stack of dependent PRs instead. Strips comment bloat so the size is honest, proposes layers from the import graph, then builds the branch chain and opens one request per layer targeting the layer below. Works from committed history or an uncommitted working tree. Creates a stack; use {{REPO}}-restack to repair one that already exists.
allowed-tools: Read Grep Glob Bash Edit
disable-model-invocation: true
---

Turn one oversized change into a stack of dependent requests, each small enough that a human will actually read it. The whole value is in the seams: a split into layers that each build, test, and make sense alone is a gift to the reviewer, and a split into layers that only mean something together is worse than the big PR you started with.

Nothing here is destructive if you follow Phase 1 — the original work is preserved on a backup branch before anything is edited or carved, and the stack is verified to reproduce it exactly.

## Phase 0: Find the work and normalize it

Everything downstream carves from a **single reference commit**, so establish one first.

1. `git status --porcelain` — is there uncommitted work?
2. `git rev-list --count origin/{{BASE_BRANCH}}..HEAD` — are there commits ahead of the base?
3. Normalize to one tip:
   - **Committed only** → the tip is `HEAD`.
   - **Uncommitted only, or both** → commit everything onto the current branch as a single throwaway commit (`git add -A && git commit -m "wip: pre-split snapshot"`). That commit is the tip. It never gets pushed; it exists so the split has a fixed thing to carve from and so nothing is riding in the working tree while you switch branches.
4. **Check ownership.** `git log origin/{{BASE_BRANCH}}..<tip> --format='%an' | sort -u`. If the work includes commits by someone else, stop and confirm before restructuring it — a split rewrites their commits into branches with your name on the carving.

## Phase 1: Build the safety net

Do this **before** the comment pass, not just before the carve — Phase 2 edits source files, and it needs the same undo everything else here has.

1. `git branch <branch>-prestack <tip>` — a full backup of the original work, and the only undo you need (`git reset --hard <branch>-prestack`).
2. Record `git rev-parse <tip>` and report both to the user before touching anything.
3. Keep this branch until the entire stack has landed. It is not cleanup to delete; it's the recovery path if a layer turns out to be carved wrong three PRs deep.

## Phase 2: Strip the comment bloat, then decide

Comments inflate a diff without adding anything a reviewer has to reason about, and a change padded with narration can look like it needs splitting when the code inside it doesn't. So the size question gets asked *after* the padding is gone, never before.

1. **Tighten the comments this change added.** **Read `comment-cleanup.md`, shipped alongside the `{{REPO}}-precommit` skill, and follow it exactly — do not strip comments from memory.** The headline rule is that a regular comment may run to at most two sentences (one is better) and a docstring to at most five, and that a comment which only restates what the code plainly does gets deleted outright. The file also carries the guardrails that matter more than the limits: **string and template literals are not comments** (a long prompt string is data the program uses at runtime), commented-out code is left alone, and license headers, shebangs, and pragmas like `# noqa` or `eslint-disable` are never touched. If you are not certain a line is a natural-language source comment, leave it.

   Only touch comments **this change added**. Pre-existing narration elsewhere in a file you edited is someone else's commit and not your business here.

2. **Commit the cleanup on its own.** `git commit -m "chore: tighten comments"`, separate from everything else. It is not part of any layer, and folding it into one buries a whole-diff edit inside a PR about something else.

   **This commit is now `<tip>`** — the ref every later phase carves from and verifies against. Re-record `git rev-parse HEAD`. `<branch>-prestack` still points at the *pre-cleanup* work and stays that way: it's the undo for the comment pass as well as the carve, which is exactly why it isn't the thing Phase 5 compares against.

3. **Measure what's actually left.** Run `klaussy split-prep --base {{BASE_BRANCH}}`. It reports code lines separately from comment and docstring lines, flags the files where comment is still most of what changed, and proposes layers from the import graph. **Decide on the code-lines figure, not the raw one.** If the `klaussy` CLI isn't on PATH, fall back to `klaussy review-prep`, or to `git diff {{BASE_BRANCH}}...HEAD --stat` while discounting generated files yourself — and say which fallback you used, since the layer proposal is unavailable in both.

4. **Judge on shape, not just size.** Around 400 **code** lines is where a split starts paying for itself, but the number is a prompt to think, not a rule:
   - **Split** when the diff contains units a reviewer could evaluate independently — a schema change under an API change under a UI change, or a mechanical rename sitting alongside real logic.
   - **Don't split** when the diff is large but uniform (a codemod, a generated client, a formatting sweep) — that reviews faster as one PR with a note explaining the pattern. Don't split a cohesive unit that only makes sense whole, either.

5. **Say so if the answer is no**, including when the cleanup is what brought it under the line — "1,240 lines, 830 after stripping 410 lines of comment; one PR is fine" is a genuinely useful answer. Report the size, name what you'd have cut along, and explain why the seams aren't there. Keep the cleanup commit, delete the backup branch, and stop. A bad split costs more review time than the big PR did.

## Phase 3: Propose the split, and get approval

**Start from `split-prep`'s proposal, then argue with it.** The layers it printed come from the actual import graph — Python parsed with `ast`, JS/TS from its import and require statements — so a file it puts in layer 1 genuinely imports nothing else in the change. That beats guessing from paths, and it is not the last word:

- **It sees static imports only.** Runtime wiring produces no edge — DI containers, plugin registries, dynamic imports, template and string references, URL routing tables, migrations ordered by filename. Those dependencies are real and you have to add them yourself.
- **Files it lists as ungraphed** (SQL, config, Go, anything outside Python and JS/TS) aren't placed at all. Put them in a layer by hand using the ladder below, and suspect them first when a layer fails to build.
- **Cycles are marked with ⟲.** Those files import each other, so no cut exists between them — they move as a unit or not at all.
- **A layer per topological level is usually too many layers.** The graph tells you what *may* be separated, not what's *worth* separating. Merge adjacent levels freely to land in the 2–5 range below.

Then present the plan **before creating anything**.

**Order layers bottom-up by dependency.** The bottom layer must not reference anything above it. Where the graph is silent, these are the natural seams, in the order they usually stack:

- Types, schema, migrations, config
- Data access and models
- Business logic and services
- API routes and handlers
- UI and client code
- Tests that only cover the top layer's behavior (tests for a layer belong *in* that layer)

**Two more seams that cut across the list, and are usually the highest-value cuts available:**

- **Mechanical apart from meaningful.** A rename, a file move, or a signature change touching 60 files reviews in seconds when it's alone and buries the real logic when it isn't.
- **Refactor apart from behavior.** Restructuring in one layer and the new behavior in the next lets a reviewer confirm the first changed nothing.

**Sizing:** aim for layers under ~300 reviewable lines and a stack of **2–5** layers. Past five, rebase churn and serialized review latency cost more than the big PR did. Never split a cohesive unit to hit a number — an uneven stack with honest seams beats an even one with invented ones.

Present the plan as a map with a per-layer line count and a one-line rationale, then wait for approval:

```
{{BASE_BRANCH}}
  └─ <branch>-1-schema      ~120 lines   migration + model fields, no callers yet
      └─ <branch>-2-api     ~240 lines   routes and handlers reading the new fields
          └─ <branch>-3-ui  ~180 lines   the form, plus its component tests
```

A wrong seam here is expensive to undo once three PRs are open. Confirm it.

## Phase 4: Carve the layers

Work bottom-up, one layer at a time, branching each off the previous one.

**If the existing commits already map cleanly onto layers** (each commit belongs wholly to one layer), cherry-pick:

```
git checkout -b <branch>-1-schema origin/{{BASE_BRANCH}}
git cherry-pick <sha> <sha>
```

**Usually they don't** — one commit touches three layers, because the work wasn't written with a split in mind. Carve by content instead, taking file state straight from the tip:

```
git checkout -b <branch>-1-schema origin/{{BASE_BRANCH}}
git checkout <tip> -- path/to/schema.py migrations/
git commit
```

For a file that belongs to more than one layer, take the whole file at the tip only if the entire file is that layer's; otherwise stage part of it with `git checkout -p <tip> -- <file>` and pick the hunks. Read what you staged before committing — a hunk-level carve is where a layer quietly acquires a reference to code that doesn't exist yet.

Then each subsequent layer branches off the one below:

```
git checkout -b <branch>-2-api <branch>-1-schema
git checkout <tip> -- api/routes.py api/handlers.py
git commit
```

**Do not edit code while carving.** A split moves lines between branches; it doesn't change them. The comment pass already happened in Phase 2 and is baked into `<tip>` — don't tidy anything else on the way past, or check 1 below will fail and you won't know whether the cause was the carve or the tidying. If a layer needs a small bridge to stand alone (an import, an `__all__` entry, a stub the next layer replaces), that's part of the carve and worth calling out in the PR body. If you find an actual bug mid-split, write it down and fix it in a follow-up — a behavior change smuggled into a restructuring is invisible to review.

## Phase 5: Verify, before anything is pushed

Two checks, and neither is optional.

1. **The stack reproduces the carve source exactly.** `git diff <tip> <top-layer>` must print nothing, where `<tip>` is the post-cleanup commit from Phase 2 — **not** `<branch>-prestack`, which predates the comment pass and would differ by exactly those edits. A non-empty diff means a hunk was dropped or duplicated: find it before you push, not after review starts.

   The stack must also carry the cleanup. `git diff <branch>-prestack <top-layer>` should show *only* comment changes — if it shows code, something in the carve went wrong that check 1 couldn't see.
2. **Every layer stands alone.** Check out each branch bottom-up and run the project's build, lint, and test commands from CLAUDE.md. A layer may legitimately add code nothing calls yet; it may not leave the build or the suite broken. A failure is a wrong seam — move code between layers and re-verify. Never fix it by loosening a test or disabling a check.

If a layer can't be made to stand alone after a couple of attempts, that seam isn't real. Merge it into its neighbor and re-verify; a four-layer stack that works beats a five-layer one that doesn't.

## Phase 6: Push and open the stack

Bottom-up, one branch per command. Push each layer, then open its request against the layer below (the bottom layer targets `{{BASE_BRANCH}}`).

Each request body gets:

- **The stack map**, same shape as Phase 3, with this layer marked and the others linked once their numbers exist. A reviewer landing on layer 3 needs to know what's underneath it.
- **What this layer does**, and what it deliberately defers upward — "no caller yet, that's layer 2" pre-empts the first review comment every time.
- **Review order**, stated plainly: bottom first.

Run each body through **`{{REPO}}-humanize`** before it goes out.

{{FORGE}}

## Phase 7: Report

Give the user the stack map with request URLs in review order, the backup branch name and its recovery command, which layers were verified how, and the merge protocol: **land the bottom request first**, then run **`{{REPO}}-restack`** to rebase the rest and retarget their bases. Merging out of order puts the wrong commits in the wrong request.

Never merge the stack yourself.

## Rules

- **Confirm the split plan before creating branches.** Everything after Phase 3 assumes those seams.
- **The backup branch stays until the stack lands.** Deleting it early removes the only complete undo — and it's the undo for the comment pass too, not just the carve.
- **Size the change on code lines, never raw diff lines.** Comment bloat is the most common reason a change looks like it needs splitting when it doesn't.
- **The comment pass only touches comments this change added,** never string literals, commented-out code, headers, or pragmas — and it lands as its own commit, never inside a layer.
- **Carving never edits.** Moving lines between branches is the whole job; behavior changes belong in their own commit and their own review.
- **The import graph is evidence, not a verdict.** It misses runtime wiring entirely; a layer that builds is the only proof a seam is real.
- **Every layer builds and passes on its own,** or the seam is wrong. Fix the seam, not the test.
- **Bottom-up for everything** — carve, verify, push, open, merge.
- **Don't split someone else's commits without asking.**
- **If the repo uses a stack tool** (Graphite, git-town, spr, ghstack), create the stack with its commands so its metadata stays consistent. Say which one you found.

## When NOT to use

- The diff is large but uniform — a codemod, a generated client, a lockfile, a formatting pass. One PR with an explanatory note reviews faster than a stack.
- It only *looks* large. Run Phase 2's cleanup and measurement before concluding anything; a change that's a third narration is common, and the answer is often "tighten the comments, ship one PR".
- The change is only coherent as a whole. Say so and keep it in one request; an artificial split makes every layer harder to judge.
- A stack already exists and just needs rebasing after the base moved — that's **`{{REPO}}-restack`**.
- The work isn't written yet. Use **`{{REPO}}-plan`** and build it in stackable order from the start; splitting after the fact is strictly more work.
- The branches live in a fork or you lack push rights — the carve will succeed locally and every push will fail. Check first.
