# Lens: Security & Quality

## Look for: Security, Readability/Maintainability, Test Coverage

### Security
- Input validation gaps, trust boundary violations.
- Injection vectors: SQL, command, XSS, path traversal.
- Authentication/authorization bypasses.
- Logging or exposing sensitive data (tokens, passwords, PII).
- Insecure defaults or missing security headers.
- Cryptographic misuse (weak algorithms, hardcoded keys).

### Readability & Maintainability
- Ambiguous naming, overly clever code.
- Comment hygiene: flag comments that restate what the code plainly does, narrate obvious steps, or read as changelog / "AI-tell" notes ("// Now we handle…", "// Added to fix…"); and multi-line blocks where one short line (or none) would do. Fix = delete or condense to a one-line WHY. Do NOT flag docstrings/JSDoc on public APIs, license/file headers, or genuine "why" comments.
- Functions that are too long or do too many things.
- Magic numbers or strings without explanation.
- Dead code or unreachable branches.

### Test Coverage
- Were tests added or updated for the changes?
- Are edge cases covered?
- Are failure paths tested?
- Do tests assert meaningful behavior (not just "doesn't crash")?
- Are mocks/stubs appropriate, or do they hide real behavior?

## Additional rules

- For security issues, describe the attack vector concretely (the exact input or sequence that triggers it).
