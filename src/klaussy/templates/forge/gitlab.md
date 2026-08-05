### Forge commands (GitLab)

`origin` points at GitLab, so `glab` is the adapter and the vocabulary is merge requests and discussions rather than pull requests and review threads. Confirm a flag with `glab <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `glab issue view <n> --comments` |
| Open a request | `glab mr create --target-branch <branch> --title <title> --description <text>` |
| Request status | `glab mr view <n>` |
| CI status | `glab ci status`, then `glab ci trace <job>` on a failing job |
| Read review comments | `glab api projects/:id/merge_requests/<iid>/discussions` |
| Reply in a thread | `glab api --method POST projects/:id/merge_requests/<iid>/discussions/<discussion-id>/notes -f body=<text>` |
| Resolve a thread | `glab api --method PUT projects/:id/merge_requests/<iid>/discussions/<discussion-id> -f resolved=true` |
| Retarget a request | `glab mr update <n> --target-branch <branch>` |

Two things bite when porting a GitHub habit. API paths take the project-scoped `iid` from the MR's URL, not the global id shown in some responses. And a discussion resolves as a whole, there is no per-note resolve. If `:id` doesn't expand in the installed `glab`, pass the URL-encoded `namespace/project` instead.
