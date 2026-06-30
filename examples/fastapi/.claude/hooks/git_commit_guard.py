#!/usr/bin/env python3
"""PreToolUse guard: run format + lint before allowing a `git commit`.

Installed by klaussy into .claude/hooks/ and registered in .claude/settings.json
as a PreToolUse hook on `Bash`. The guard inspects the Bash command from the
hook payload; if it's a `git commit` invocation, the guard runs the project's
format and lint commands. Any non-zero exit blocks the commit and surfaces the
failing command's stderr back to Claude.

Commands carrying the `__KLAUSSY_PATHS__` placeholder are scoped to the files
being committed, so the gate judges only the change in flight — not pre-existing
issues elsewhere in the tree. Commands without the placeholder (e.g. a project's
own `npm run lint` script) run repo-wide as written.

Format/lint commands are baked in at scaffold time from klaussy's stack
detection. Edit this file (or re-run `klaussy hooks --force`) to change them.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# Sentinels replaced by klaussy at scaffold time. Either may end up as None
# (no detected command) or a shell command string.
FORMAT_CMD: str | None = 'ruff format __KLAUSSY_PATHS__'
LINT_CMD: str | None = 'ruff check --fix __KLAUSSY_PATHS__'
# Deterministic commented-out-code check (e.g. `ruff check --select ERA .`).
# Block-only — it flags commented-out code; it does not delete it.
COMMENT_CHECK_CMD: str | None = 'ruff check --select ERA __KLAUSSY_PATHS__'
# Deterministic verbose-comment check (block-only literal, no sentinel).
# `--diff` scopes it to lines changed vs HEAD so pre-existing comments
# elsewhere in a touched file don't block the commit.
VERBOSE_COMMENT_CMD: str | None = "klaussy comment-lint --diff __KLAUSSY_PATHS__"

# Stand-in for the files being committed; expanded just before each command runs.
PATHS_TOKEN = "__KLAUSSY_PATHS__"

# Matches `git commit` and `git -C path commit`, but not `git commitlint`,
# `git log --grep=commit`, or shell-quoted strings that mention commit.
GIT_COMMIT_RE = re.compile(r"(^|[\s;&|])git(\s+-[^\s]+\s+\S+)*\s+commit(\s|$)")


def _is_git_commit(command: str) -> bool:
    return bool(GIT_COMMIT_RE.search(command))


def _commits_all(command: str) -> bool:
    """True if the commit stages tracked changes itself (`git commit -a`/--all).

    Those files aren't in the index yet when this PreToolUse hook fires, so the
    staged-paths lookup must also include working-tree modifications.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    for tok in tokens:
        if tok == "--all":
            return True
        if tok.startswith("-") and not tok.startswith("--") and "a" in tok:
            return True
    return False


def _changed_paths(include_unstaged: bool) -> list[str]:
    """Files being committed: staged adds/copies/mods/renames, existing on disk."""
    arg_sets = [["--cached"]]
    if include_unstaged:
        arg_sets.append([])  # working tree vs index, for `git commit -a`
    found: set[str] = set()
    for extra in arg_sets:
        try:
            out = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", *extra],
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if out.returncode == 0:
            found.update(line for line in out.stdout.splitlines() if line)
    return sorted(p for p in found if os.path.exists(p))


def _resolve(cmd: str, paths: list[str]) -> str | None:
    """Expand the staged-paths placeholder; None means skip (nothing to check)."""
    if PATHS_TOKEN not in cmd:
        return cmd
    if not paths:
        return None
    return cmd.replace(PATHS_TOKEN, " ".join(shlex.quote(p) for p in paths))


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

    paths = _changed_paths(include_unstaged=_commits_all(command))
    for cmd in (FORMAT_CMD, LINT_CMD, COMMENT_CHECK_CMD, VERBOSE_COMMENT_CMD):
        if not cmd:
            continue
        resolved = _resolve(cmd, paths)
        if resolved is None:
            continue
        rc = _run(resolved)
        if rc != 0:
            print(
                f"klaussy pre-commit: `{resolved}` failed (exit {rc}). Commit blocked.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
