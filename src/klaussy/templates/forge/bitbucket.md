### Forge commands (Bitbucket / Atlassian)

`origin` points at Bitbucket, which has no first-party CLI, so there is no command to copy. Use the REST API only if the user already has credentials configured (an app password, `BITBUCKET_TOKEN`, or a `~/.netrc` entry). Otherwise ask them to paste the ticket or request content, and hand back the steps to apply on their side.

- **Bitbucket Cloud**: `https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>/pullrequests/<id>`; comments live under `/comments`; retarget with a `PUT` whose body sets `destination.branch.name`.
- **Bitbucket Data Center** (self-hosted, formerly Stash): `<host>/rest/api/1.0/projects/<key>/repos/<slug>/pull-requests/<id>`. The payload shapes differ from Cloud, so establish which one this host is before composing a call.
- **Jira tickets**: if `acli` is installed, check `acli --help` for its current interface before using it. Otherwise ask for the ticket text.

Never guess an endpoint, a payload shape, or an auth scheme here. A wrong `POST` writes a comment on the wrong request and can't be taken back; asking costs a turn.
