### Forge commands (GitHub)

`origin` points at GitHub, so the `gh` CLI is the adapter. Confirm a flag with `gh <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `gh issue view <n> --comments` |
| Open a request | `gh pr create --base <branch> --title <title> --body-file <file>` |
| Request status | `gh pr view <n> --json state,mergeable,reviewDecision,baseRefName` |
| CI status | `gh pr checks <n>`, then `gh run view <run-id> --log-failed` on a failure |
| Read review comments | `gh api repos/{owner}/{repo}/pulls/<n>/comments` |
| Reply in a thread | `gh api --method POST repos/{owner}/{repo}/pulls/<n>/comments/<comment-id>/replies -f body=<text>` |
| Resolve a thread | two steps, see below — REST can't do it |
| Retarget a request | `gh pr edit <n> --base <branch>` |

`{owner}/{repo}` are placeholders `gh` fills from the current repo, leave them literal.

**Resolving needs GraphQL, and the id it wants is not the comment id.** The REST comment objects don't carry it, so read the thread ids first, then resolve one:

```
gh api graphql -f query='{ repository(owner: "<owner>", name: "<repo>") {
  pullRequest(number: <n>) { reviewThreads(first: 50) { nodes {
    id isResolved comments(first: 1) { nodes { databaseId body } } } } } } }'

gh api graphql -f query='mutation($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }' -F id=<thread-node-id>
```

Match a thread to the comment you replied to through `comments.nodes[].databaseId`, which is the REST comment id. `threadId` is the only required input.

A reply must name the thread it answers. The `replies` endpoint above takes only `body`; the alternative is `POST .../pulls/<n>/comments` with `-F in_reply_to=<comment-id>` (an integer, hence `-F`). Posting to `comments` without `in_reply_to` opens a new top-level review comment rather than replying.

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
