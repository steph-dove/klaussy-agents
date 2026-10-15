<!-- forge:core -->
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

<!-- forge:feedback -->
#### Review feedback (GitHub)

| Need | Command |
| :--- | :--- |
| Read inline review comments | `gh api --paginate repos/{owner}/{repo}/pulls/<n>/comments` |
| Read review summaries | `gh api --paginate repos/{owner}/{repo}/pulls/<n>/reviews` |
| Read conversation comments | `gh api --paginate repos/{owner}/{repo}/issues/<n>/comments` |
| Reply in a thread | `gh api --method POST repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body=<text>` |
| Answer a conversation comment | `gh pr comment <n> --body-file <file>` (these aren't threaded, so quote or link the comment you're answering) |
| Resolve a thread | two steps, see below — REST can't do it |

**`gh pr view --json comments` is not one of these reads.** It returns conversation comments only, truncated, with no inline review comments and no review bodies. Use the three `gh api --paginate` reads above.

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

<!-- forge:stacks -->
**GitHub has native stacks**, driven by the `gh-stack` extension. `gh extension list` says whether it's installed. If it isn't, **offer to install it** — `gh extension install github/gh-stack`, one command, no repo changes — and say what it buys before asking: a stack map and layer navigation on every request page, plus cascading rebase when the base moves. Ask rather than installing unprompted, since it touches the user's `gh` setup and not this repo, but do ask; silently settling for bare chained bases hands back a worse result than the one command would have. Declining is a fine answer and the fallback below still works.

The extension is in public preview, so check `gh stack <command> --help` before relying on a flag.

| Need | Command |
| :--- | :--- |
| Link requests that already exist into a stack | `gh stack link --base <branch> <branch-or-pr> <branch-or-pr> ...` |
| Track a carved chain locally | `gh stack init --base <branch> <branch> ...` |
| Push the tracked chain and open or update its requests | `gh stack submit` |
| See the stack | `gh stack view` |
| Cascading rebase after the base moved | `gh stack rebase` |
| Fetch, rebase, push, and sync in one pass | `gh stack sync` |

Arguments run bottom-up, nearest the base first. Two constraints decide whether a stack is available at all: **every branch must live in this repo** (cross-fork stacks aren't supported), and the extension has to be installed.

`link` and `init` are two different entry points and the difference shows up later. `link` stacks requests that already exist and leaves nothing behind locally, so a later `gh stack rebase` needs `gh stack checkout <stack-number>` first to pick the stack back up. `init` registers the branches locally up front and `submit` then opens the requests itself, which means the bodies are its own — write them with `gh pr edit <n> --body-file` afterwards if they have to say something specific.

Without it, chained `--base` targets still give reviewers a per-layer diff, and GitHub often offers to convert an eligible chain into a stack — a banner on the request, or "Add to stack" behind the stack icon. Say which route you took.

<!-- forge:media -->
#### Attaching QA media (GitHub)

Upload each screenshot and recording to GitHub's attachment store, where a file dragged into a comment box goes, and embed the URL that comes back. Uploading posts nothing; the file only shows up where you embed it.

```
gh api repos/{owner}/{repo} --jq .id

gh api -X POST "https://uploads.github.com/user-attachments/assets?name=<file-name>&repository_id=<repo-id>" \
  -H "Content-Type: <mime-type>" --input <path> --jq .url
```

- **Pass the full `https://uploads.github.com/...` URL.** A bare path goes to `api.github.com` and fails.
- **Set the real type:** `image/png`, `image/jpeg`, `image/gif`, `video/mp4`, `video/webm` or `video/quicktime`.
- **Embed images as `<img src="<url>" width="420" alt="<what it shows>">`** so a before/after pair fits side by side in a table. **Put a video's URL on a line of its own**: GitHub renders a bare attachment URL as a player, and a Markdown link or `<video>` tag doesn't get one.
- **Who can see the files follows the repo.** A private repo's attachments load only for signed-in people with access.
- **Limits:** 10 MB per image, and 10 MB per video on free plans (100 MB on paid ones). Trim a long recording rather than skipping it.
- **The endpoint isn't in GitHub's REST docs.** If it returns anything but `201`, don't try another host; list the files still to attach by hand, with their paths.
