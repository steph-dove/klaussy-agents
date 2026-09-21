<!-- forge:core -->
### Forge commands (GitLab)

`origin` points at GitLab, so `glab` is the adapter and the vocabulary is merge requests and discussions rather than pull requests and review threads. Confirm a flag with `glab <command> --help` before running one you haven't used in this repo; CLI interfaces drift between versions.

| Need | Command |
| :--- | :--- |
| Read a ticket | `glab issue view <n> --comments` |
| Open a request | `glab mr create --target-branch <branch> --title <title> --description <text>` |
| Request status | `glab mr view <n>` |
| CI status | `glab ci status`, then `glab ci trace <job>` on a failing job |
| Retarget a request | `glab mr update <n> --target-branch <branch>` |

Two things bite when porting a GitHub habit:

- **API paths take the project-scoped `iid`** from the MR's URL, not the global id that appears in some responses. If `:id` doesn't expand in the installed `glab`, pass the URL-encoded `namespace/project` instead.
- **`-f` and `-F` are easy to swap.** `-f/--raw-field` sends a literal string, `-F/--field` infers the type. Booleans like `resolved=true` need `-F`, or GitLab receives the string `"true"`.

`glab mr create` has no `--body-file`. `--description` takes the text directly (a lone `-` opens an editor), so a body written to a file has to be passed as text.

<!-- forge:feedback -->
#### Review feedback (GitLab)

| Need | Command |
| :--- | :--- |
| Read review comments | `glab api --paginate projects/:id/merge_requests/<iid>/discussions` |
| Reply in a thread | `glab api --method POST projects/:id/merge_requests/<iid>/discussions/<discussion-id>/notes -f body=<text>` |
| Resolve a thread | `glab api --method PUT projects/:id/merge_requests/<iid>/discussions/<discussion-id> -F resolved=true` |

- **Discussions are paged, 20 at a time.** Without `--paginate` a busy request returns only the first page. The list covers both line comments and overview-tab comments, so it's the one read you need.
- **Resolving is per-discussion by default.** `PUT .../discussions/<id>` with `resolved` closes the whole thread; a single note is resolved through `PUT .../discussions/<id>/notes/<note-id>` instead. Pick deliberately, they aren't interchangeable.

<!-- forge:stacks -->
**There is no native stack object to register.** A stack on GitLab is exactly a chain of `--target-branch` values, each request aimed at the branch below it, so the chain and the map you write into each description are the only things a reviewer navigates by. Get the targets right and say plainly that the stack is branch-chained.
