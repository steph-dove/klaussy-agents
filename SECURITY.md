# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use one of these private channels:

- **Preferred:** GitHub's private vulnerability reporting — go to the
  **Security** tab of this repo and click **"Report a vulnerability."**
- **Email:** `doverstephaniem@gmail.com` with the subject line
  `[security] klaussy-agents`.

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a proof of concept is ideal).
- The klaussy version (`klaussy --version`) and your OS / Python version.

We'll acknowledge your report as soon as we can, keep you updated, and credit
you in the release notes once a fix ships (unless you'd prefer to stay
anonymous). Please give us a reasonable window to release a fix before any
public disclosure.

## Supported versions

Security fixes are released against the **latest version** on PyPI. Always run
the newest release: `pipx upgrade klaussy-agents` (or `uv tool upgrade
klaussy-agents`).

## Scope notes

klaussy generates files and installs **git hooks** and **agent hooks** into the
repos you run it against, and detects/bakes in project commands (lint, format,
commented-out-code checks). Reports are especially welcome about: command
injection via detected/baked commands, the read-injection guard, the
git-commit guard, the pre-plan guidance hook, file-write paths, or the bundled
MCP server.
