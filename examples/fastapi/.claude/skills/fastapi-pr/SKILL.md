---
name: fastapi-pr
description: Use when the user wants a PR description generated for the current branch. Reads commit history, file changes, and CLAUDE.md, fills the repo's own pull/merge request template when it has one, and writes the result to pr-description.md. Also known as `klaussy-pr`.
allowed-tools: Read Grep Glob Bash(git *) Bash(klaussy base *) Bash(python3 -m klaussy *) Bash(python -m klaussy *) Write
---

## Branch

```!
git branch --show-current
```

## Base

```!
klaussy base --explain
```

## Commit history and files changed

Both ranges need `<base>`, so run them yourself: `git log <base>..HEAD --oneline` and `git diff <base>...HEAD --stat`.

## Instructions

Generate a PR description for the changes summarized above. Extract any ticket reference (e.g. FEAT-1234) from the branch name. Read CLAUDE.md for project conventions and any PR template rules. For key changed files, read them to understand the full context — do not paraphrase from the diff alone.

**Resolve the base first, by running the command.** Every range below is against `<base>`. Run `klaussy base --explain` before any range and reuse its answer; if the `klaussy` command isn't found, try `python3 -m klaussy base --explain` (`python -m klaussy` on Windows), then `git symbolic-ref --short refs/remotes/origin/HEAD` without its `origin/` prefix, and `master` if that's empty too. **Don't work the base out by eye.** Picking the obvious branch gets the same answer most of the time and misses the case that matters: the command also reports branches `HEAD` may have been cut from, and a branch stacked on another one gets a range covering commits your change never added. If it names any, say so and ask which base to use rather than picking. Either way, state the base you used, and that you checked.

### Use the repo's own template if it has one

Look for one before writing anything: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE/` (a directory of them), the same three names at the repo root or under `docs/`, and for GitLab `.gitlab/merge_request_templates/*.md`.

When one exists it wins outright. Keep its headings, their order, and their exact wording, fill each section with real content, and leave its checklists and HTML comments in place, ticking only what you've actually confirmed. A template is the reviewers' agreement about what a PR says; replacing it with the house format below throws that away and reads as though you didn't look. If the directory form holds several, pick the one whose name matches the change and say which you used.

Only when there is no template, use this format:

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
- **A short PR gets a short description.** One bullet under Changes is a fine answer for a one-file fix; padding it out to fill the template wastes the reviewer's time. Drop the Notes section entirely when there's nothing a reviewer needs flagged, rather than writing "N/A" or inventing something. Section names the repo's own template asks for are the exception: leave those in place and say briefly why one is empty, since a reviewer scanning for a heading they expect will notice it missing.
- If there are database changes, call them out explicitly.
- If there are new dependencies, mention them.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

Write the output to `pr-description.md` in the repo root.

## When NOT to use

- The user wants the PR or MR opened for real — this skill only writes the description text into a file, so hand the file to whichever create command their host takes.
- The branch has no commits ahead of `<base>` — there's nothing to describe; tell the user instead.
- The user wants a release-notes-style summary spanning multiple PRs — different shape; don't try to fit it in this template.
