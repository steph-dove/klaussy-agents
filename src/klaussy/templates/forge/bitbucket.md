### Forge commands (Bitbucket / Atlassian)

`origin` points at Bitbucket, which has no first-party CLI — Atlassian's `acli` covers Jira only. The REST API is the adapter, so these are `curl` calls, and they need credentials: an app password (`curl -u <user>:<app-password>`), a `BITBUCKET_TOKEN` bearer, or a `~/.netrc` entry. If none is configured, ask the user rather than hunting for one.

Everything below is Bitbucket **Cloud**, base `https://api.bitbucket.org/2.0`, with `<ws>` the workspace and `<repo>` the slug.

| Need | Call |
| :--- | :--- |
| Read a ticket | `acli jira workitem view` (Jira only, confirm flags with `--help`) |
| Open a request | `POST /repositories/<ws>/<repo>/pullrequests` with `title` and `source.branch.name` |
| Request status | `GET /repositories/<ws>/<repo>/pullrequests/<id>` — `state` is `OPEN`/`MERGED`/`DECLINED` |
| CI status | `GET /repositories/<ws>/<repo>/pipelines?sort=-created_on`, then `/pipelines/<uuid>/steps` for a failing run |
| Read review comments | `GET /repositories/<ws>/<repo>/pullrequests/<id>/comments` |
| Reply in a thread | `POST …/comments` with `{"content": {"raw": "<text>"}, "parent": {"id": <comment-id>}}` |
| Resolve a thread | `POST …/comments/<comment-id>/resolve` (`DELETE` the same path reopens it) |
| Retarget a request | `PUT …/pullrequests/<id>` with `{"destination": {"branch": {"name": "<branch>"}}}` |

Four things worth knowing before you use these:

- **Threading is `parent`, not a separate endpoint.** A reply is an ordinary comment carrying `parent.id`; omit it and the comment lands at top level. Inline comments carry an `inline` object with `path` and line numbers.
- **Only open pull requests can be mutated.** The retarget `PUT` is documented for changing a request's branches, but a merged or declined request rejects it.
- **A `200` on that `PUT` is not proof.** Bitbucket accepts the whole pull-request object as the body and quietly ignores fields it won't change, so send only what you're changing and then re-read the request to confirm `destination.branch.name` actually moved.
- **Bitbucket Data Center is a different API.** Self-hosted (formerly Stash) serves `<host>/rest/api/1.0/projects/<key>/repos/<slug>/pull-requests/<id>` with different payload shapes, and none of the above is verified against it. Establish which one this host is first, and check that instance's own API docs before composing a call.
