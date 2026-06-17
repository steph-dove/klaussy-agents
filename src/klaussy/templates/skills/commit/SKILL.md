---
name: {{REPO}}-commit
description: Use when the user wants a commit message written for currently staged changes. Reads `git diff --cached`, recent log style, and CLAUDE.md, then outputs a conventional-commit-style message — type(scope) summary + why-focused body.
allowed-tools: Read Bash(git diff *) Bash(git log *) Bash(git branch *)
disable-model-invocation: true
---

## Staged changes

```!
git diff --cached --stat
```

```!
git diff --cached
```

## Recent commit style

```!
git log --oneline -10
```

## Current branch

```!
git branch --show-current
```

## Instructions

Write a commit message for the changes shown above. Read CLAUDE.md for any project-specific commit conventions before writing.

Format:

```
<type>(<scope>): <short summary>

<body — explain what changed and why, not how>
```

Types: feat, fix, refactor, test, docs, chore, style, perf
Scope: the area of code affected (e.g. auth, api, ui)

Rules:
- Summary line under 72 characters.
- Body wraps at 80 characters.
- Match the style of the recent commits shown above.
- Focus on "why" in the body, not "what" (the diff already shows "what").
- If the branch name has a ticket reference (e.g. FEAT-1234), include it in the body.

Output ONLY the commit message, nothing else. Do not wrap it in code blocks.

## When NOT to use

- The user wants to actually run `git commit` — this skill only writes the message text.
- Nothing is staged — ask the user to stage changes first instead of inventing a message.
- The user wants a commit message for unstaged or unmerged changes — point them at `git add` first.
