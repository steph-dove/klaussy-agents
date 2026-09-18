---
name: {{REPO}}-security-audit
description: Use when the user wants a focused security pass over the current change — scanning the branch diff for leaked secrets, injection and SSRF, broken access control, unsafe deserialization, and newly added or vulnerable dependencies. Narrower and deeper than the general review skill: it applies only the security lenses and reports findings; it does not refactor or fix.
allowed-tools: Read Grep Glob Bash(git diff *) Bash(git log *)
---

You are running a security audit of the current change. Scope is the diff against the base branch and the immediate context of what it touches — not the whole tree, and not style or architecture. Report findings only; do not edit code.

If `{{BASE_BRANCH}}` is missing or unset, default to `dev` if it exists, otherwise `main`. Read the change with `git diff {{BASE_BRANCH}}...HEAD` first.

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

{{HUMANIZE}}
