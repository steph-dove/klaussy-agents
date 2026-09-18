---
name: {{REPO}}-explain
description: Use when the user wants code, a concept, or the current diff explained in this repo. With no specific target, explains the current branch diff; with a target, traces call chains and data flow end-to-end and explains in plain language.
allowed-tools: Read Grep Glob Bash(git diff *)
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, explain the current branch diff using the dump below. Otherwise, treat `$ARGUMENTS` as the target — a file path, function name, or concept — and explain that.

## Current branch diff (used when target is empty)

```!
git diff {{BASE_BRANCH}}...HEAD
```

## Instructions

**If the target is empty (no arguments):**
1. The diff above shows everything changed on this branch. If it's empty, fall back to `git diff` (unstaged) and `git diff --cached` (staged).
2. Read the full files involved to understand the surrounding context — do not paraphrase from the diff alone.
3. Lead with two or three sentences: what the change does and why. Then add only what the diff won't tell them — how the moving parts interact, and any non-obvious behavior or edge case it introduces. If there's nothing non-obvious, stop after the lead. That's a complete answer, not a short one.

**If the target is provided:**
1. Read CLAUDE.md and any matching `.claude/rules/*.md` for the area the target lives in.
2. Find the relevant code using Grep and Glob.
3. Read the full files involved to understand context.
4. Trace the call chain and data flow end-to-end.
5. Lead with two or three sentences answering the question directly. Then go deeper only where the code doesn't speak for itself: a component interaction that isn't visible from one file, a design decision with a live trade-off, an edge case that would surprise the reader. Skip the parts they can read for themselves.

## Rules

- Tailor the depth to the question — "what does this function do" needs less than "how does auth work". Answer at the length you'd answer out loud; nobody asking a one-line question wants a document back.
- Don't structure a short answer. Headings and bullet lists on three paragraphs of prose make it harder to read, not easier. Reach for them only when the explanation is genuinely long and the reader needs to navigate it.
- Use concrete examples from the code, not abstract descriptions.
- Cite file:line references when pointing at code.
- If something looks like a bug or smells off, mention it once, then stay focused on explaining.
- Don't suggest changes unless asked.

{{HUMANIZE}}

## When NOT to use

- The user wants to *change* code — use the implement, refactor, debug, or fix skill instead.
- The user wants a code review — use the review skill, which validates findings and structures output.
- The user wants the diff itself, not an explanation of it — they can run `git diff` directly.
