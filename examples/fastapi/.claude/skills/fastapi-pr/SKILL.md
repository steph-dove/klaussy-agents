---
name: fastapi-pr
description: Use when the user wants a PR description generated for the current branch. Reads commit history, file changes, and CLAUDE.md, then writes a Summary / Changes / Test Plan / Notes block to pr-description.md. Also known as `klaussy-pr`.
allowed-tools: Read Grep Glob Bash(git *) Write
---

## Branch

```!
git branch --show-current
```

## Commit history vs base

```!
git log master..HEAD --oneline
```

## Files changed

```!
git diff master...HEAD --stat
```

## Instructions

Generate a PR description for the changes summarized above. Extract any ticket reference (e.g. FEAT-1234) from the branch name. Read CLAUDE.md for project conventions and any PR template rules. For key changed files, read them to understand the full context — do not paraphrase from the diff alone.

Output format:

```markdown
## Summary

<!-- 1-3 sentences explaining what this PR does and why -->

## Changes

<!-- Key changes, grouped logically. Aim for 3-6 bullets; one line each. -->

## Visual QA / Evidence (for UI & visual changes)

<!-- Include Before & After comparison table and responsive demo video -->
| Before | After |
| :---: | :---: |
| ![Before](image-url) | ![After](image-url) |

<!-- Demo Video: [Watch Full Interaction Video](video-url) -->

## Test Plan

<!-- How the changes were tested -->
- [ ] Tests pass locally
- [ ] Manually verified

## Notes

<!-- Anything reviewers should pay attention to, migration steps, feature flags, etc. -->
```

Rules:
- **Write for a reviewer who has 30 seconds.** Lead with what changed and why it matters; surface the one thing they must look at. The Summary should orient them before they open a single file.
- **Don't echo the diff.** The reviewer can read the diff. Summarize intent and group related changes — do not narrate every edit line by line.
- **Describe the current end state, not a changelog.** Write what the PR *is*, not a chronological story of how you got there ("first I tried X, then changed to Y"). If you revised an approach mid-branch, describe only the final shape.
- Be specific — reference actual file names, functions, and components.
- Focus on the "why" not just the "what".
- If the branch name has a ticket reference, include it in the summary.
- Keep it concise. No filler.
- **A short PR gets a short description.** One bullet under Changes is a fine answer for a one-file fix; padding it out to fill the template wastes the reviewer's time. Drop the Notes section entirely when there's nothing a reviewer needs flagged, rather than writing "N/A" or inventing something.
- If there are database changes, call them out explicitly.
- If there are new dependencies, mention them.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

Write the output to `pr-description.md` in the repo root.

## When NOT to use

- The user wants the PR or MR opened for real — this skill only writes the description text into a file, so hand the file to whichever create command their host takes.
- The branch has no commits ahead of `master` — there's nothing to describe; tell the user instead.
- The user wants a release-notes-style summary spanning multiple PRs — different shape; don't try to fit it in this template.
