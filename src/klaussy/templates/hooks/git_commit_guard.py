#!/usr/bin/env python3
"""PreToolUse guard: run format + lint before allowing a `git commit`.

Installed by klaussy into .claude/hooks/ and registered in .claude/settings.json
as a PreToolUse hook on `Bash`. The guard inspects the Bash command from the
hook payload; if it's a `git commit` invocation, the guard runs the project's
format and lint commands. Any non-zero exit blocks the commit and surfaces the
failing command's stderr back to Claude.

Format/lint commands are baked in at scaffold time from klaussy's stack
detection. Edit this file (or re-run `klaussy hooks --force`) to change them.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

# Sentinels replaced by klaussy at scaffold time. Either may end up as None
# (no detected command) or a shell command string.
FORMAT_CMD: str | None = "__KLAUSSY_FORMAT_CMD__"
LINT_CMD: str | None = "__KLAUSSY_LINT_CMD__"
# Deterministic commented-out-code check (e.g. `ruff check --select ERA .`).
# Block-only — it flags commented-out code; it does not delete it.
COMMENT_CHECK_CMD: str | None = "__KLAUSSY_COMMENT_CHECK_CMD__"

# Matches `git commit` and `git -C path commit`, but not `git commitlint`,
# `git log --grep=commit`, or shell-quoted strings that mention commit.
GIT_COMMIT_RE = re.compile(r"(^|[\s;&|])git(\s+-[^\s]+\s+\S+)*\s+commit(\s|$)")


def _is_git_commit(command: str) -> bool:
    return bool(GIT_COMMIT_RE.search(command))


def _run(cmd: str) -> int:
    print(f"klaussy pre-commit: running `{cmd}`", file=sys.stderr)
    result = subprocess.run(shlex.split(cmd))
    return result.returncode


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if (payload.get("hook_event_name") or payload.get("event")) != "PreToolUse":
        return 0
    if (payload.get("tool_name") or payload.get("tool")) != "Bash":
        return 0

    tool_input = payload.get("tool_input") or payload.get("input") or {}
    command = tool_input.get("command", "")
    if not _is_git_commit(command):
        return 0

    for cmd in (FORMAT_CMD, LINT_CMD, COMMENT_CHECK_CMD):
        if not cmd:
            continue
        rc = _run(cmd)
        if rc != 0:
            print(
                f"klaussy pre-commit: `{cmd}` failed (exit {rc}). Commit blocked.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
