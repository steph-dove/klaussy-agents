---
name: httpx-security-audit
description: Use when the user wants a focused security pass over the current change — scanning the branch diff for leaked secrets, injection and SSRF, broken access control, unsafe deserialization, and newly added or vulnerable dependencies. Narrower and deeper than the general review skill — it applies only the security lenses and reports findings; it does not refactor or fix. Also known as `klaussy-security-audit`.
allowed-tools: Read Grep Glob Bash(git diff *) Bash(git log *) Bash(git symbolic-ref *) Bash(klaussy base *) Bash(python3 -m klaussy *) Bash(python -m klaussy *)
---

You are running a security audit of the current change. Scope is the diff against the base branch and the immediate context of what it touches — not the whole tree, and not style or architecture. Report findings only; do not edit code.

**Resolve the base first, by running the command.** Every range below is against `<base>`. Run `klaussy base --explain` before any range and reuse its answer; if the `klaussy` command isn't found, try `python3 -m klaussy base --explain` (`python -m klaussy` on Windows), then `git symbolic-ref --short refs/remotes/origin/HEAD` without its `origin/` prefix, and `master` if that's empty too. **Don't work the base out by eye.** Picking the obvious branch gets the same answer most of the time and misses the case that matters: the command also reports branches `HEAD` may have been cut from, and a branch stacked on another one gets a range covering commits your change never added. If it names any, say so and ask which base to use rather than picking. Either way, state the base you used, and that you checked.

Read the change with `git diff <base>...HEAD` first. Auditing the wrong range means reporting someone else's commits as this change's findings.

## Lenses

Apply each lens to the ADDED and changed lines. A finding must point to a concrete line, not a general worry.

**1. Secrets & credentials** (Severity: High)
- API keys, tokens, passwords, private keys, connection strings with embedded credentials, or high-entropy literals that look like real secrets in added lines. Obvious placeholders (`YOUR_API_KEY`, `xxx`, `changeme`) are not findings.

**2. Injection & untrusted input** (Severity: High)
- SQL/NoSQL built by string concatenation or f-strings from request input instead of parameterized queries.
- Shell execution from untrusted input (`shell=True`, string-built commands, `eval`/`exec`).
- Command, path-traversal, template, or header injection where user input reaches a sink unsanitized.

**3. SSRF & outbound requests** (Severity: High)
- A request URL, host, or port derived from user input without an allowlist — especially fetches that could reach internal addresses or metadata endpoints.

**4. Access control & authn/authz** (Severity: High)
- A new endpoint, handler, or operation that skips the auth/permission check its peers apply.
- Authorization decided on client-supplied data (role/owner from the request body), missing object-level ownership checks (IDOR), or a check that's logged but not enforced.

**5. Unsafe deserialization & data handling** (Severity: High)
- `pickle`, `yaml.load` (non-safe), `eval`-based parsing, or native deserialization of untrusted bytes.
- Disabled TLS verification (`verify=False`), weak crypto/hashing for security purposes (MD5/SHA1 for passwords, hardcoded IVs).

**6. Dependencies** (Severity: Medium unless a known CVE → High)
- New dependencies added in this diff (manifest or lockfile). For each, ask: is it necessary, maintained, and from a trusted source? Flag typosquat-looking names and duplicates of a library already vendored.
- Pinned-to-vulnerable or wildcard version ranges introduced by the change.

## Output

For each finding: `file:line`, the lens, a one-line description of the exploit path, and the minimal fix. Order by severity. If a lens is clean, say so in one line rather than padding. If the diff has no security-relevant surface, state that plainly.

Out of scope: naming, formatting, performance, test coverage, and anything outside the diff. Do not propose refactors and do not edit files — this is a read-only audit.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `httpx-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `httpx-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.
