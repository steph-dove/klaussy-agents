#!/usr/bin/env python3
"""PreToolUse guard: humanize a comment before the agent posts it.

Installed by klaussy into .claude/hooks/ and registered in .claude/settings.json
as a PreToolUse hook on `Bash`. A `--body` literal is rewritten through
`updatedInput`, so the command runs cleaned with no extra round trip; a
`--body-file` is scrubbed in place unless git reports it tracked, so a committed
doc is never mutated. Pure stdlib; scrubbing shells out to `klaussy humanize`,
the same implementation the skill and CLI use. If that isn't on PATH, or the
body is neither a plain literal nor a readable file, the command runs unchanged.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

# `gh` subcommands that post user-visible prose we want humanized.
_COMMENT_SUBCOMMANDS = (
    "pr comment",
    "issue comment",
    "pr review",
    "pr create",
    "pr edit",
    "issue create",
    "issue edit",
)
_BODY_FLAGS = ("-b", "--body")
_BODY_FILE_FLAGS = ("-F", "--body-file")


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


# Shell operators that end one command and start the next.
_SEPARATORS = ";&|"


def _split_commands(command: str) -> list[str]:
    """Split a shell line into its separate commands, respecting quotes.

    Segmenting has to happen on the raw string: shlex only emits a separator as
    its own token when it's space-padded, so `gh pr comment 1 --body "x"; git
    commit -F msg` leaves git's `-F` inside the gh segment and the guard scrubs
    the commit message instead. Splitting on tokens that merely *contain* a
    separator isn't an option either — a markdown table body is one quoted token
    full of `|`.
    """
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            # Inside double quotes a backslash escapes the next character, so
            # \" is body text and must not be read as the closing quote. Inside
            # single quotes the shell treats a backslash literally, so it isn't.
            if ch == chr(92) and quote == '"' and i + 1 < len(command):
                buf.append(ch)
                buf.append(command[i + 1])
                i += 2
                continue
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch == chr(92) and i + 1 < len(command):  # backslash escape
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in _SEPARATORS:
            parts.append("".join(buf))
            buf = []
            while i < len(command) and command[i] in _SEPARATORS:
                i += 1
            continue
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p for p in parts if p.strip()]


def _find_body_file(tokens: list[str]) -> str | None:
    """Locate the path passed to `--body-file` / `-F`, if any."""
    for i, tok in enumerate(tokens):
        if tok in _BODY_FILE_FLAGS and i + 1 < len(tokens):
            return tokens[i + 1]
        if tok.startswith("--body-file="):
            return tok[len("--body-file=") :]
    return None


def _humanize(text: str) -> str | None:
    """Scrub via `klaussy humanize`; None if it can't run (missing/failed)."""
    try:
        result = subprocess.run(["klaussy", "humanize"], input=text, capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _is_untracked(path: str) -> bool | None:
    """Whether the file is free of version control, so rewriting it is safe.

    git runs with `-C` at the file's own directory, so the answer is about the
    repo that owns the file rather than the agent's cwd. Only exit 0 (tracked)
    stops a rewrite. git failing to run at all answers None rather than False,
    so the caller can say the check didn't run instead of claiming the file is
    tracked — either way we post unscrubbed rather than overwrite a doc the user
    can't get back.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        result = subprocess.run(
            ["git", "-C", directory, "ls-files", "--error-unmatch", "--", os.path.basename(path)],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode == 0:
        return False  # git tracks it
    if result.returncode == 1:
        return True  # a repo that doesn't track it
    if "not a git repository" in (result.stderr or "").lower():
        return True  # nothing version-controls this directory
    # Any other fatal (dubious ownership, unreadable index, a broken git
    # wrapper) is git failing, not git answering. Treating it as untracked
    # would overwrite a committed doc on the strength of an error.
    return None


def _write_atomic(path: Path, text: str) -> bool:
    """Replace the file's contents atomically. False if the write failed.

    A plain write truncates first, so a failure part-way through would hand `gh`
    a half-written body to post.
    """
    tmp = path.with_name(path.name + ".klaussy-tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _humanize_file(path: str) -> tuple[str, bool] | None:
    """Scrub a `--body-file` in place.

    Returns (note, scrubbed) when there's something to report. `scrubbed` is
    True once the file holds the humanized body, and False when the body still
    has tells and is about to post that way — the caller decides how loudly to
    say so. None means there was nothing worth reporting.
    """
    if path == "-" or any(ch in path for ch in "$`"):
        return None
    try:
        original = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    cleaned = _humanize(original)
    if cleaned is None or cleaned == original:
        return None
    # The body has tells, so every outcome gets a note: staying quiet here reads
    # as "already clean". Notes describe the file, never the command's fate —
    # one caller allows the post and the other blocks it.
    untracked = _is_untracked(path)
    if untracked is None:
        # Don't dress a missing git up as a version-control decision — the user
        # needs to know the check couldn't run, not that the file is tracked.
        return (
            f"klaussy comment guard: couldn't check git for {path}, so it wasn't scrubbed.",
            False,
        )
    if not untracked:
        return (f"klaussy comment guard: {path} is tracked, so it wasn't scrubbed.", False)
    if not _write_atomic(Path(path), cleaned):
        return (f"klaussy comment guard: couldn't rewrite {path}, so it wasn't scrubbed.", False)
    return (f"klaussy comment guard: humanized {path}.", True)


def main() -> int:
    try:
        _raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        payload = json.loads(_raw.decode("utf-8", "replace") if isinstance(_raw, bytes) else _raw)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return 0

    if (payload.get("hook_event_name") or payload.get("event")) != "PreToolUse":
        return 0
    if (payload.get("tool_name") or payload.get("tool")) != "Bash":
        return 0

    tool_input = payload.get("tool_input") or payload.get("input") or {}
    command = tool_input.get("command", "")
    if not _is_comment_post(command):
        return 0

    parts = _split_commands(command)
    notes: list[str] = []

    for part in parts:
        if not _is_comment_post(part):
            continue
        try:
            tokens = shlex.split(part)
        except ValueError:
            continue

        # File-backed body: fix the file, leave the command alone. Checked first
        # because it's the shape anything multi-line actually uses, and because
        # it needs no command rewrite, so chaining can't make it unsafe.
        body_file = _find_body_file(tokens)
        if body_file is not None:
            reported = _humanize_file(body_file)
            if reported:
                notes.append(reported[0])
            continue

        found = _find_body(tokens)
        if found is None:
            continue
        idx, body, inline = found
        # Only humanize plain literals — a body with shell expansion isn't ours
        # to rewrite (we'd be scrubbing the template, not the rendered text).
        if any(ch in body for ch in "$`"):
            continue
        cleaned = _humanize(body)
        if cleaned is None or cleaned == body:
            continue

        if len(parts) > 1:
            # Rewriting one command out of a chained line means reassembling the
            # others, and shlex.join doesn't round-trip the operators between
            # them. Report rather than post a body we know has tells.
            notes.append(
                "klaussy comment guard: the body in this chained command has AI "
                "tells and was left as-is. Post it as its own command, or write "
                "it to a file and use --body-file, to have it humanized."
            )
            continue

        new_tokens = list(tokens)
        new_tokens[idx] = "--body=" + cleaned if inline else cleaned
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": {"command": shlex.join(new_tokens)},
                    }
                }
            )
        )
        return 0

    if notes:
        print(json.dumps({"systemMessage": " ".join(notes)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
