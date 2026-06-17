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
3. Explain what changed and why, covering:
   - The purpose of the changes as a whole
   - How the modified components interact
   - Any non-obvious behavior or edge cases introduced

**If the target is provided:**
1. Read CLAUDE.md and any matching `.claude/rules/*.md` for the area the target lives in.
2. Find the relevant code using Grep and Glob.
3. Read the full files involved to understand context.
4. Trace the call chain and data flow end-to-end.
5. Explain how it works in plain language, covering:
   - What it does and why it exists
   - Key components and how they interact
   - Important design decisions or trade-offs
   - Any non-obvious behavior or edge cases

## Rules

- Tailor the depth to the question — "what does this function do" needs less than "how does auth work".
- Use concrete examples from the code, not abstract descriptions.
- Cite file:line references when pointing at code.
- If something looks like a bug or smells off, mention it once, then stay focused on explaining.
- Don't suggest changes unless asked.

## When NOT to use

- The user wants to *change* code — use the implement, refactor, debug, or fix skill instead.
- The user wants a code review — use the review skill, which validates findings and structures output.
- The user wants the diff itself, not an explanation of it — they can run `git diff` directly.
