---
name: {{REPO}}-self-review
description: Use right before declaring an implementation done — a last-pass review of your OWN uncommitted change against a fixed checklist (reuse, stdlib, comments, dead code, tests, scope). Catches the things that make a diff read as AI-written before a human ever sees it. Reviews the current diff; it does not write new features.
allowed-tools: Read Grep Glob Bash
---

Review the change you just made before you call it complete. This is the gate between "I wrote code" and "it's done" — run it on your own diff and fix what it surfaces, don't just report.

## Step 1: Get the diff

Look at exactly what changed — `git diff` (unstaged), `git diff --cached` (staged), and untracked files. Read the full changed files, not only the hunks; a problem often lives in the context around an edit.

## Step 2: Walk the checklist

Go through every item against the diff. For each, either confirm it holds or fix it now.

**Reuse before reinvention**
- Does this add a function, helper, type, or constant that already exists somewhere in the repo? Search first, then reuse it instead.
- Is any logic duplicated from another module? Call the existing code, don't copy it.

**Built-ins and existing dependencies**
- Did you hand-roll something the standard library or an already-installed dependency provides (deep-clone, debounce, grouping, UUID, HTTP, parsing, date math)? Replace it with the built-in.
- Did you add a new third-party dependency? That's a decision to raise with the user, not to slip in — flag it.

**Comments**
- One line, and only where it earns its place: a *why*, a gotcha, an invariant, a link. Delete comments that restate the code, narrate steps, or read as changelog ("Now we handle…", "Added to fix…").
- Prefer a clearer name over a comment.

**Dead code and leftovers**
- No commented-out code, no unused variables/imports/functions, no debug prints or `console.log`/`dbg!` scaffolding, no stray TODO/FIXME without a reference.

**Tests**
- New behavior has tests (happy path + error/edge paths). A bug fix has a test that fails without the fix. Run the suite from CLAUDE.md and confirm it's green.

**Scope and minimalism**
- Every changed line serves the task. No unrelated refactoring, renaming, or reformatting rode along. Revert what isn't yours to change.

**Conventions and correctness**
- Matches the repo's existing patterns, naming, and structure (and any `.claude/rules/*.md` covering the touched files).
- Errors are surfaced, not swallowed — no empty catches, no fallback values that hide a failure.

## Step 3: Report the verdict

State plainly: what you fixed on this pass, and confirm the checklist now holds (or name any item you consciously left and why). If nothing needed fixing, say so — a clean pass is a valid result, not a reason to invent changes.

## Rules

- Fix, don't just flag — this runs on your own work, so finish the job.
- Do NOT expand scope while reviewing: this pass tightens the existing change, it doesn't add features.
- Be honest. The point is to catch your own misses before a human does, not to rubber-stamp.

## When NOT to use

- There's no uncommitted change to review — nothing to do.
- The user wants a review of *someone else's* PR or branch — use the review skill (it's built for that, with severity levels and validation).
- The change is a pure docs/prose edit with no code — the humanize skill fits better.
