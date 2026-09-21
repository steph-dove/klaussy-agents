---
name: httpx-address-review
description: Use when a PR has review feedback and the user wants it addressed — pull the review comments, triage each one, apply the changes it warrants, then commit, push, and post a humanized reply per comment. Closes the loop between a review and the follow-up commit; it does not re-review the code from scratch. Also known as `klaussy-address-review`.
---

Address the review feedback on the current PR. Every comment gets a response: a change, or a reasoned reply explaining why not. Don't silently skip any.

## Phase 1: Gather the feedback

1. **Get the review comments** for the current branch's request, using the adapter below. Pull the inline (line-level) comments, the summary review bodies, and the general conversation comments; the inline ones are where the substance usually is, but a request made in the conversation is just as binding. Fetch every page: a partial read drops comments without any error. If there's no request yet, no CLI, or no credentials, ask the user to paste the feedback and carry on from there.
2. **Read CLAUDE.md** and any `.claude/rules/*.md` covering the touched files — a fix must still satisfy the repo's conventions.
3. **Build the change list.** For each comment, capture: the file/line, what's asked, and the reviewer's intent (not just the literal words). Group comments that touch the same code so you fix each spot once.

### Forge commands (GitHub)

`origin` points at GitHub, so the `gh` CLI is the adapter. Confirm a flag with `gh <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `gh issue view <n> --comments` |
| Open a request | `gh pr create --base <branch> --title <title> --body-file <file>` |
| Request status | `gh pr view <n> --json state,mergeable,reviewDecision,baseRefName` |
| CI status | `gh pr checks <n>`, then `gh run view <run-id> --log-failed` on a failure |
| Retarget a request | `gh pr edit <n> --base <branch>` |

`{owner}/{repo}` are placeholders `gh` fills from the current repo, leave them literal.

#### Review feedback (GitHub)

| Need | Command |
| :--- | :--- |
| Read inline review comments | `gh api --paginate repos/{owner}/{repo}/pulls/<n>/comments` |
| Read review summaries | `gh api --paginate repos/{owner}/{repo}/pulls/<n>/reviews` |
| Read conversation comments | `gh api --paginate repos/{owner}/{repo}/issues/<n>/comments` |
| Reply in a thread | `gh api --method POST repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body=<text>` |
| Answer a conversation comment | `gh pr comment <n> --body-file <file>` (these aren't threaded, so quote or link the comment you're answering) |
| Resolve a thread | two steps, see below — REST can't do it |

**Feedback lives in three places, and each list is paged.** Inline comments, review summary bodies, and comments on the conversation tab are separate endpoints; read all three, since a reviewer who writes "please also rename X" in the conversation expects it handled like a line comment. Without `--paginate` each call returns only the first 30, so a busy request silently loses the rest. Pages print as separate JSON arrays; add `--slurp` when piping to `jq` and you want one.

**Resolving needs GraphQL, and the id it wants is not the comment id.** The REST comment objects don't carry it, so read the thread ids first, then resolve one:

```
gh api graphql --paginate -f query='query($endCursor: String) {
  repository(owner: "<owner>", name: "<repo>") { pullRequest(number: <n>) {
    reviewThreads(first: 100, after: $endCursor) {
      pageInfo { hasNextPage endCursor }
      nodes { id isResolved comments(first: 1) { nodes { databaseId body } } } } } } }'

gh api graphql -f query='mutation($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }' -F id=<thread-node-id>
```

Match a thread to the comment you replied to through `comments.nodes[].databaseId`, which is the REST comment id. `threadId` is the only required input.

A reply must name the thread it answers. The `replies` endpoint above takes only `body`; the alternative is `POST .../pulls/<n>/comments` with `-F in_reply_to=<comment-id>` (an integer, hence `-F`). Posting to `comments` without `in_reply_to` opens a new top-level review comment rather than replying.

## Phase 2: Triage each comment

Sort every comment into one of:

- **Accept & fix** — a real issue or a clear improvement. Most comments.
- **Accept with a different fix** — the concern is valid but the reviewer's suggested change isn't the best one; do the better fix and say why in the reply.
- **Discuss / decline** — you believe the current code is correct, or the change is out of scope. This is legitimate, but it requires a specific, respectful reason, not a dismissal. When unsure whether to decline, ask the user rather than deciding unilaterally.

State the triage before editing, so the user can redirect if they disagree.

## Phase 3: Apply the changes

1. **Make each accepted change** as a minimal, targeted edit — fix what the comment raised, don't refactor around it.
2. **Check for siblings.** If a comment points at a pattern (not just one line), grep for the same pattern elsewhere in the diff and fix those too, unless the reviewer scoped it to the one spot.
3. **Re-verify after editing** — run the tests/lint from CLAUDE.md. A fix that breaks the suite isn't done.
4. **Keep the changes reviewable.** One logical follow-up; don't fold in unrelated work that a re-review would have to untangle.

## Phase 4: Reply, post, and hand off

1. **Draft a reply per comment** (or per group): what you changed and where, or — for a decline — the specific reason. One sentence is the target; two is the ceiling. "Fixed, moved the check into `validate_session`." is a complete reply.
2. **Humanize every reply before it goes out.** Run the drafts through **`httpx-humanize`**. A reply that reads as generated is the most visible way this skill can embarrass the user, and a posted comment can't be quietly taken back. This is a gate, not a suggestion: nothing posts until it's done.
3. **Commit and push** the changes (`fix: address review feedback`, or per the repo convention).
4. **Post each humanized reply** in its thread with the adapter's reply command. Answer a conversation comment where it was made, not as a line comment.
5. **Summarize** for the user: which comments led to changes, which were declined and why, and the commit and reply links. A few lines, not a report; they can read the diff.

Leave the threads for the reviewer to resolve, and don't re-request review, unless the user asks for either.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `httpx-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `httpx-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

## Rules

- Humanize before posting. Every reply is public and permanent; that pass is what keeps it reading like a person wrote it.
- Respond to every comment — a change or a reason. Silence on a comment reads as ignoring the reviewer.
- Critique the code, never the reviewer; when you decline, give evidence, not a brush-off. Read a blunt comment for its substance, not its tone, and reply civilly regardless.
- Don't over-correct: fix what was raised, not the whole file. Scope creep in a review-response commit makes the re-review harder.
- If two comments conflict, or a comment contradicts CLAUDE.md, surface the conflict to the user instead of silently picking one.

## When NOT to use

- There's no review yet — the user wants their branch reviewed; use the review skill.
- The feedback is a full redesign, not line comments — that's a re-plan; use the plan skill.
- The user only wants the reply text drafted, not the code changed — draft the replies and skip the edit phase.
