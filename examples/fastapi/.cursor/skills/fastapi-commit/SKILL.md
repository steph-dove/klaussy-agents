---
name: fastapi-commit
description: Use when the user wants a commit message written for currently staged changes. Reads `git diff --cached`, recent log style, and CLAUDE.md, then outputs a conventional-commit-style message — type(scope) summary + why-focused body. Also known as `klaussy-commit`.
---

## Staged changes

Run `git diff --cached --stat` and use its output.

Run `git diff --cached` and use its output.

## Recent commit style

Run `git log --oneline -10` and use its output.

## Current branch

Run `git branch --show-current` and use its output.

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
- **Skip the body when the subject already says it.** A rename, a version bump, a typo fix needs one line. Write a body only when there's a why the subject can't carry, and keep it to a sentence or two.
- If the branch name has a ticket reference (e.g. FEAT-1234), include it in the body.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

Output ONLY the commit message, nothing else. Do not wrap it in code blocks.

## When NOT to use

- The user wants to actually run `git commit` — this skill only writes the message text.
- Nothing is staged — ask the user to stage changes first instead of inventing a message.
- The user wants a commit message for unstaged or unmerged changes — point them at `git add` first.
