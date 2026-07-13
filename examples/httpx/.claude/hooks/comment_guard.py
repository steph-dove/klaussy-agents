#!/usr/bin/env python3
"""PreToolUse guard: humanize a comment before the agent posts it.

Installed by klaussy into .claude/hooks/ and registered in .claude/settings.json
as a PreToolUse hook on `Bash`. When the agent is about to post a comment via
`gh` (`gh pr comment`, `gh issue comment`, `gh pr review`), the guard extracts
the comment body, runs it through klaussy's deterministic humanize scrubber, and
— if the scrubber would change it — rewrites the command so the *posted* comment
has no AI tells. The rewrite uses the PreToolUse `updatedInput` field, so it's
transparent: Claude's command runs with the cleaned body, no extra round trip.

Pure stdlib; the scrubbing itself shells out to `klaussy humanize` (stdin →
stdout), the same canonical implementation the humanize skill and CLI use. If
`klaussy` isn't on PATH, or the body isn't a plain literal, the guard allows the
command unchanged — it never blocks a post on its own account.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys

# `gh` subcommands that post user-visible prose we want humanized.
_COMMENT_SUBCOMMANDS = ("pr comment", "issue comment", "pr review")
_BODY_FLAGS = ("-b", "--body")


def _is_comment_post(command: str) -> bool:
    return "gh" in command and any(sub in command for sub in _COMMENT_SUBCOMMANDS)


def _find_body(tokens: list[str]) -> tuple[int, str, bool] | None:
    """Locate the literal comment body. Returns (token_index, body, inline).

    `inline` is True for the `--body=VALUE` form (value lives in the same token);
    False for the `--body VALUE` / `-b VALUE` form (value is the next token).
    """
    for i, tok in enumerate(tokens):
        if tok in _BODY_FLAGS and i + 1 < len(tokens):
            return (i + 1, tokens[i + 1], False)
        if tok.startswith("--body="):
            return (i, tok[len("--body=") :], True)
    return None


def _humanize(text: str) -> str | None:
    """Scrub via `klaussy humanize`; None if it can't run (missing/failed)."""
    try:
        result = subprocess.run(
            ["klaussy", "humanize"], input=text, capture_output=True, text=True
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    try:
        _raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        payload = json.loads(_raw.decode("utf-8", "replace") if isinstance(_raw, bytes) else _raw)
    except (json.JSONDecodeError, ValueError):
        return 0

    if (payload.get("hook_event_name") or payload.get("event")) != "PreToolUse":
        return 0
    if (payload.get("tool_name") or payload.get("tool")) != "Bash":
        return 0

    tool_input = payload.get("tool_input") or payload.get("input") or {}
    command = tool_input.get("command", "")
    if not _is_comment_post(command):
        return 0

    try:
        tokens = shlex.split(command)
    except ValueError:
        return 0
    found = _find_body(tokens)
    if not found:
        return 0
    idx, body, inline = found

    # Only humanize plain literals — a body with shell expansion isn't ours to
    # rewrite (we'd be scrubbing the template, not the rendered text).
    if any(ch in body for ch in "$`"):
        return 0

    cleaned = _humanize(body)
    if cleaned is None or cleaned == body:
        return 0

    new_tokens = list(tokens)
    new_tokens[idx] = "--body=" + cleaned if inline else cleaned
    new_command = shlex.join(new_tokens)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": {"command": new_command},
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
