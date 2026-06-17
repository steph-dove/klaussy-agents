---
name: {{REPO}}-pr
description: Use when the user wants a PR description generated for the current branch. Reads commit history, file changes, and CLAUDE.md, then writes a Summary / Changes / Test Plan / Notes block to pr-description.md.
allowed-tools: Read Grep Glob Bash(git *) Write
disable-model-invocation: true
---

## Branch

```!
git branch --show-current
```

## Commit history vs base

```!
git log {{BASE_BRANCH}}..HEAD --oneline
```

## Files changed

```!
git diff {{BASE_BRANCH}}...HEAD --stat
```

## Instructions

Generate a PR description for the changes summarized above. Extract any ticket reference (e.g. FEAT-1234) from the branch name. Read CLAUDE.md for project conventions and any PR template rules. For key changed files, read them to understand the full context — do not paraphrase from the diff alone.

Output format:

```markdown
## Summary

<!-- 1-3 sentences explaining what this PR does and why -->

## Changes

<!-- Bullet list of key changes, grouped logically -->

## Test Plan

<!-- How the changes were tested -->
- [ ] Tests pass locally
- [ ] Manually verified

## Notes

<!-- Anything reviewers should pay attention to, migration steps, feature flags, etc. -->
```

Rules:
- Be specific — reference actual file names, functions, and components.
- Focus on the "why" not just the "what".
- If the branch name has a ticket reference, include it in the summary.
- Keep it concise. No filler.
- If there are database changes, call them out explicitly.
- If there are new dependencies, mention them.

Write the output to `pr-description.md` in the repo root.

## When NOT to use

- The user wants to actually open a PR (`gh pr create`) — this skill only writes the description text into a file.
- The branch has no commits ahead of `{{BASE_BRANCH}}` — there's nothing to describe; tell the user instead.
- The user wants a release-notes-style summary spanning multiple PRs — different shape; don't try to fit it in this template.
