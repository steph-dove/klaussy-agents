#!/usr/bin/env python3
"""Cross-agent pre-shell guard: run format + lint before a `git commit`.

Installed by klaussy into a target agent's hooks directory and wired to that
agent's "before shell/tool" event (Gemini BeforeTool, Cursor
beforeShellExecution, Codex PreToolUse, Copilot preToolUse). The guard pulls the
shell command out of the hook payload — whose shape differs per agent — checks
whether it's a `git commit`, and if so runs the project's format and lint
commands. A non-zero exit blocks the commit (exit code 2 + stderr is honored as
a block by all supported agents) and surfaces the failing command back.

Hardened to never crash: any unexpected payload or error exits 0 (allow). This
matters because some agents (e.g. Copilot preToolUse) treat a crashing hook as a
*deny of every tool call*. Pure stdlib so the repo stays portable.

Format/lint commands are baked in at scaffold time. Edit this file (or re-run
`klaussy hooks --force --agents <agent>`) to change them.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

# Sentinels replaced by klaussy at scaffold time. Any may be None.
FORMAT_CMD: str | None = "__KLAUSSY_FORMAT_CMD__"
LINT_CMD: str | None = "__KLAUSSY_LINT_CMD__"
# Deterministic commented-out-code check (block-only; flags, never deletes).
COMMENT_CHECK_CMD: str | None = "__KLAUSSY_COMMENT_CHECK_CMD__"

# Matches `git commit` / `git -C path commit`, not `git commitlint` or a quoted
# string that merely mentions commit.
GIT_COMMIT_RE = re.compile(r"(^|[\s;&|])git(\s+-[^\s]+\s+\S+)*\s+commit(\s|$)")


def _is_git_commit(command: str) -> bool:
    return bool(GIT_COMMIT_RE.search(command))


def _extract_command(payload: dict) -> str:
    """Pull the shell command string out of any supported agent's payload.

    Known locations:
      * Claude / Gemini / Codex / Copilot(VS Code): tool_input.command
      * Copilot CLI (camelCase):                    toolArgs.command / toolArgs
      * Cursor beforeShellExecution:                command (top level)
      * Legacy alias:                               input.command
    """
    for container_key in ("tool_input", "toolArgs", "input"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            value = container.get("command")
            if isinstance(value, str) and value:
                return value
        elif isinstance(container, str) and container:
            # Some Copilot CLI shell tools pass the command as toolArgs directly.
            return container
    top = payload.get("command")
    if isinstance(top, str):
        return top
    return ""


def _run(cmd: str) -> int:
    print(f"klaussy pre-commit: running `{cmd}`", file=sys.stderr)
    try:
        return subprocess.run(shlex.split(cmd)).returncode
    except (OSError, ValueError) as exc:
        # Can't run the check (command missing / unparseable) — don't block the
        # commit on our own failure; surface a note and allow.
        print(f"klaussy pre-commit: could not run `{cmd}`: {exc}", file=sys.stderr)
        return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        command = _extract_command(payload)
        if not _is_git_commit(command):
            return 0
        for cmd in (FORMAT_CMD, LINT_CMD, COMMENT_CHECK_CMD):
            if not cmd:
                continue
            rc = _run(cmd)
            if rc != 0:
                print(
                    f"klaussy pre-commit: `{cmd}` failed (exit {rc}). "
                    "Commit blocked.",
                    file=sys.stderr,
                )
                return 2
        return 0
    except Exception as exc:  # never crash — see module docstring
        print(f"klaussy pre-commit guard error (allowing): {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
