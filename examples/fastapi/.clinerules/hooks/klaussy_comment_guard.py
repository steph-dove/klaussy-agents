#!/usr/bin/env python3
"""Cross-agent pre-shell guard: humanize a comment before the agent posts it.

Installed by klaussy into a target agent's hooks directory and wired to that
agent's "before shell/tool" event (Gemini BeforeTool, Cursor
beforeShellExecution, Codex PreToolUse, Copilot preToolUse, Antigravity
run_command). When the agent is about to post a comment via `gh` (`gh pr
comment`, `gh issue comment`, `gh pr review`), the guard scrubs the comment body
with klaussy's deterministic humanizer.

Unlike Claude's PreToolUse hook, these agents' protocols can't rewrite the tool
input, so the guard can't humanize in place. Instead it BLOCKS the post (exit 2
+ stderr, which every supported agent honors) and hands back the humanized
command for the agent to re-issue. A body that's already clean — or one the
guard can't scrub (no `klaussy` on PATH, shell-expanded body) — is allowed
through untouched.

Hardened to never crash: any unexpected payload or error exits 0 (allow), since
some agents (e.g. Copilot preToolUse) treat a crashing hook as a deny of every
tool call. Pure stdlib; scrubbing shells out to `klaussy humanize`.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys

_COMMENT_SUBCOMMANDS = ("pr comment", "issue comment", "pr review")
_BODY_FLAGS = ("-b", "--body")


def _extract_command(payload: dict) -> str:
    """Pull the shell command string out of any supported agent's payload."""
    for container_key in ("tool_input", "toolArgs", "input"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            value = container.get("command")
            if isinstance(value, str) and value:
                return value
        elif isinstance(container, str) and container:
            return container
    top = payload.get("command")
    if isinstance(top, str):
        return top
    return ""


def _is_comment_post(command: str) -> bool:
    return "gh" in command and any(sub in command for sub in _COMMENT_SUBCOMMANDS)


def _find_body(tokens: list[str]) -> tuple[int, str, bool] | None:
    for i, tok in enumerate(tokens):
        if tok in _BODY_FLAGS and i + 1 < len(tokens):
            return (i + 1, tokens[i + 1], False)
        if tok.startswith("--body="):
            return (i, tok[len("--body=") :], True)
    return None


def _humanize(text: str) -> str | None:
    try:
        result = subprocess.run(
            ["klaussy", "humanize"], input=text, capture_output=True, text=True
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    try:
        _raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        payload = json.loads(_raw.decode("utf-8", "replace") if isinstance(_raw, bytes) else _raw)
        if not isinstance(payload, dict):
            return 0
        command = _extract_command(payload)
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
        if any(ch in body for ch in "$`"):
            return 0
        cleaned = _humanize(body)
        if cleaned is None or cleaned == body:
            return 0

        new_tokens = list(tokens)
        new_tokens[idx] = "--body=" + cleaned if inline else cleaned
        print(
            "klaussy comment guard: this comment has AI tells. Re-post the "
            "humanized version:\n" + shlex.join(new_tokens),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # never crash — see module docstring
        print(f"klaussy comment guard error (allowing): {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
