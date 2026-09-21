# Split by hand

Use this for layers `klaussy split-carve` can't carve (a file whose hunks belong to different layers), or when `klaussy` isn't on PATH. The split-pr SKILL.md's rules still apply: no code edits while carving, and hooks off for the carve.

## Carve the layers by hand

Work bottom-up, one layer at a time, branching each off the previous one.

**If the existing commits already map cleanly onto layers** (each commit belongs wholly to one layer), cherry-pick:

```
git checkout -b <branch>-1-schema origin/master
git cherry-pick <sha> <sha>
```

**Usually they don't** — one commit touches three layers, because the work wasn't written with a split in mind. Carve by content instead, taking file state straight from the tip:

```
git checkout -b <branch>-1-schema origin/master
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

## Verify by hand

1. **The stack reproduces the carve source exactly.** `git diff <tip> <top-layer>` must print nothing, where `<tip>` is the post-cleanup commit from Phase 2 — **not** `<branch>-prestack`, which predates the comment pass and would differ by exactly those edits. A non-empty diff means a hunk was dropped or duplicated: find it before you push, not after review starts.

   The stack must also carry the cleanup. `git diff <branch>-prestack <top-layer>` should show *only* comment changes — if it shows code, something in the carve went wrong that check 1 couldn't see.

2. **Every layer stands alone.** Check out each branch bottom-up and run the project's build, lint, and test commands from CLAUDE.md. A layer may legitimately add code nothing calls yet; it may not leave the build or the suite broken. A failure is a wrong seam — move code between layers and re-verify. Never fix it by loosening a test or disabling a check.
