### Forge commands (Bitbucket / Atlassian)

`origin` points at Bitbucket, which has no first-party CLI, so there is no command to copy. Use the REST API only if the user already has credentials configured (an app password, `BITBUCKET_TOKEN`, or a `~/.netrc` entry). Otherwise ask them to paste the ticket or request content, and hand back the steps to apply on their side.

- **Bitbucket Cloud**: `https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>`; comments live under `/comments`.
- **Bitbucket Data Center** (self-hosted, formerly Stash): `<host>/rest/api/1.0/projects/<key>/repos/<slug>/pull-requests/<id>`. The payload shapes differ from Cloud, so establish which one this host is before composing a call.
- **Jira tickets**: `acli jira workitem view` (the Atlassian CLI covers Jira only, it has no Bitbucket pull-request commands). Confirm the flags with `acli jira workitem view --help`. Without it, ask for the ticket text.

**Retargeting is the one to be careful with.** A `PUT` to the pull request is the documented way to change its destination branch, but Atlassian's reference doesn't spell out which fields are updatable, and the update is known to return `200` while silently ignoring parts of the body. Never report a retarget as done on the strength of a status code: re-read the pull request and confirm the destination actually changed, or hand the user the one-click path (the destination branch name in the PR header is editable in the UI).

Never guess an endpoint, a payload shape, or an auth scheme here. A wrong `POST` writes a comment on the wrong request and can't be taken back; asking costs a turn.
