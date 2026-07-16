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
import shutil
import subprocess
import sys

# Sentinels replaced by klaussy at scaffold time. Either may end up as None
# (no detected command) or a shell command string.
FORMAT_CMD: str | None = "__KLAUSSY_FORMAT_CMD__"
LINT_CMD: str | None = "__KLAUSSY_LINT_CMD__"
# Deterministic commented-out-code check (e.g. `ruff check --select ERA .`).
# Block-only — it flags commented-out code; it does not delete it.
COMMENT_CHECK_CMD: str | None = "__KLAUSSY_COMMENT_CHECK_CMD__"
# Deterministic verbose-comment check (block-only literal, no sentinel).
# `--diff` scopes it to lines changed vs HEAD so pre-existing comments
# elsewhere in a touched file don't block the commit.
VERBOSE_COMMENT_CMD: str | None = "klaussy comment-lint --diff __KLAUSSY_PATHS__"
# Deterministic function-local import check (block-only literal, no sentinel).
# `--diff` scopes it to changed lines so a pre-existing local import elsewhere
# in a touched file doesn't block the commit.
IMPORT_LINT_CMD: str | None = "klaussy import-lint --diff __KLAUSSY_PATHS__"
# Deterministic secret scan (block-only literal, no sentinel). `--diff` scopes it
# to added lines so a pre-existing value elsewhere in a touched file doesn't block
# the commit.
SECRET_SCAN_CMD: str | None = "klaussy secret-scan --diff __KLAUSSY_PATHS__"

# Stand-in for the files being committed; expanded just before each command runs.
PATHS_TOKEN = "__KLAUSSY_PATHS__"

# Exit code meaning "I couldn't run" rather than "I found problems": an unknown
# subcommand, a bad flag, a broken config. ruff, eslint and Typer/Click all
# reserve 1 for findings and 2 for this, so a check that exits 2 hasn't judged
# the diff and can't be treated as a failure of it.
USAGE_EXIT = 2

# Per-tool file suffixes, used to drop staged paths a tool can't parse before it
# runs — so a `.md` committed with Python never reaches `ruff` (which would fail
# to parse it and wrongly block the commit). Unlisted tools get every path.
PY_EXTS = (".py", ".pyi")
JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue")
TOOL_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "ruff": PY_EXTS,
    "black": PY_EXTS,
    "isort": PY_EXTS,
    "flake8": PY_EXTS,
    "pylint": PY_EXTS,
    "mypy": PY_EXTS,
    "pyright": PY_EXTS,
    "eslint": JS_EXTS,
}

# Command tokens that front a tool rather than being one, skipped when sniffing
# which tool a command runs (so `npx eslint` → `eslint`, `uv run ruff` → `ruff`).
RUNNER_TOKENS = frozenset(
    {
        "npx",
        "npm",
        "pnpm",
        "yarn",
        "bun",
        "bunx",
        "uv",
        "uvx",
        "poetry",
        "pipx",
        "python",
        "python3",
        "run",
        "exec",
        "tool",
        "-m",
    }
)

# Matches `git commit` and `git -C path commit`, but not `git commitlint`,
# `git log --grep=commit`, or shell-quoted strings that mention commit.
GIT_COMMIT_RE = re.compile(r"(^|[\s;&|])git(\s+-[^\s]+\s+\S+)*\s+commit(\s|$)")

# Conventional Commits: type(scope)!: subject. The repo mandates this format;
# an inline `-m` message that doesn't match blocks the commit.
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: .+"
)


def _command_tool(cmd: str) -> str | None:
    """Best-effort name of the tool a command invokes (basename, lowercased)."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    for tok in tokens:
        if tok.startswith("-") or tok in RUNNER_TOKENS:
            continue
        return os.path.basename(tok).lower()
    return None


def _applicable_paths(cmd: str, paths: list[str]) -> list[str]:
    """Subset of `paths` the command's tool can process; all paths if unknown."""
    exts = TOOL_EXTENSIONS.get(_command_tool(cmd) or "")
    if not exts:
        return paths
    return [p for p in paths if p.lower().endswith(exts)]


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


def _skips_verify(command: str) -> bool:
    """True if the commit opts out of hooks (`git commit --no-verify`/`-n`).

    `--no-verify` tells git to skip its own pre-commit/commit-msg hooks; this
    guard is the same kind of gate, so an explicit opt-out is honored — we run
    nothing and stay silent (relevant when an agent passes `--no-verify` to
    avoid the guard's output flooding its context). Mirrors `_commits_all`'s
    combined-short-flag handling so `-an`/`-nm` are caught, not just `-n`.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    for tok in tokens:
        if tok == "--no-verify":
            return True
        if tok.startswith("-") and not tok.startswith("--") and "n" in tok:
            return True
    return False


def _commit_messages(command: str) -> list[str]:
    """Subjects passed via -m/--message on the commit command, in order.

    Only inline messages are visible to a pre-commit hook; an editor-based commit
    (no -m) has no message yet, so it can't be validated and is allowed. Handles
    `-m foo`, `-mfoo`, `--message foo`, `--message=foo`, and combined short flags
    like `-am foo`.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    msgs: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-m", "--message"):
            if i + 1 < len(tokens):
                msgs.append(tokens[i + 1])
                i += 2
                continue
        elif tok.startswith("--message="):
            msgs.append(tok[len("--message=") :])
        elif tok.startswith("-") and not tok.startswith("--") and "m" in tok:
            after = tok[tok.index("m") + 1 :]
            if after:
                msgs.append(after)
            elif i + 1 < len(tokens):
                msgs.append(tokens[i + 1])
                i += 2
                continue
        i += 1
    return msgs


def _bad_commit_message(subject: str) -> str:
    """Block notice for a non-Conventional-Commits subject line."""
    return (
        "klaussy pre-commit: commit message must follow Conventional Commits "
        "(type(scope): subject), e.g. `feat(auth): add SSO`. Allowed types: feat, "
        "fix, docs, style, refactor, perf, test, build, ci, chore, revert. Fix the "
        f"message, or re-commit with `--no-verify` to skip. Got: {subject!r}"
    )


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
    """Expand the staged-paths placeholder, scoped to files the tool understands.

    None means skip the command — either it has no placeholder (nothing staged
    to inject) or, after filtering to the tool's file types, nothing being
    committed is applicable (e.g. a Markdown-only commit gives ruff no Python)."""
    if PATHS_TOKEN not in cmd:
        return cmd
    applicable = _applicable_paths(cmd, paths)
    if not applicable:
        return None
    return cmd.replace(PATHS_TOKEN, " ".join(shlex.quote(p) for p in applicable))


def _run(cmd: str) -> int:
    """Run a check, inheriting its stdout/stderr so its own output is the record.

    A missing or unparseable command can't judge the diff, so it allows the
    commit silently rather than block — and without printing, to keep the guard
    quiet on every commit (verbose per-command chatter floods an agent's
    context, especially with many staged files)."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return 0
    if not tokens:
        return 0
    # Resolve via PATH first so Windows PATHEXT is honored — a `ruff.exe` or
    # Node shim `eslint.cmd` is found instead of fail-opening the gate. A
    # .cmd/.bat shim isn't a real executable image, so it must run via cmd.exe.
    exe = shutil.which(tokens[0])
    if exe is None:
        return 0  # tool not installed — can't judge the diff, so allow silently
    if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
        argv = ["cmd", "/c", exe, *tokens[1:]]
    else:
        argv = [exe, *tokens[1:]]
    try:
        return subprocess.run(argv).returncode
    except (OSError, ValueError):
        return 0


def _check_name(cmd: str) -> str:
    """The check's name for a message — `klaussy import-lint`, `ruff check`."""
    try:
        tokens = [t for t in shlex.split(cmd) if not t.startswith("-")]
    except ValueError:
        return "a check"
    return " ".join(tokens[:2]) if tokens else "a check"


def _skipped_message(cmd: str) -> str:
    """Notice that a check couldn't run, so the commit wasn't judged by it.

    Said out loud rather than passed over in silence: a skipped secret scan that
    looks like a clean one is worse than a noisy line.
    """
    return (
        f"klaussy pre-commit: `{_check_name(cmd)}` exited with a usage error, so that "
        "check was SKIPPED — not passed. The tool is likely older than this guard "
        "(upgrade it) or misconfigured. Commit allowed."
    )


def _blocked_message(cmd: str) -> str:
    """One-line block notice. The failing tool's own output already printed
    above, so we deliberately don't echo the resolved command and its (possibly
    long) file list — that repetition is what floods context."""
    tool = _command_tool(cmd) or "a check"
    return (
        f"klaussy pre-commit: {tool} reported problems above — fix them, or "
        "re-commit with `--no-verify` to skip this gate."
    )


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
    if not _is_git_commit(command):
        return 0
    if _skips_verify(command):
        return 0

    subjects = _commit_messages(command)
    if subjects and not CONVENTIONAL_RE.match(subjects[0]):
        print(_bad_commit_message(subjects[0]), file=sys.stderr)
        return 2

    paths = _changed_paths(include_unstaged=_commits_all(command))
    for cmd in (
        SECRET_SCAN_CMD,
        FORMAT_CMD,
        LINT_CMD,
        COMMENT_CHECK_CMD,
        VERBOSE_COMMENT_CMD,
        IMPORT_LINT_CMD,
    ):
        if not cmd:
            continue
        resolved = _resolve(cmd, paths)
        if resolved is None:
            continue
        rc = _run(resolved)
        if rc == USAGE_EXIT:
            print(_skipped_message(cmd), file=sys.stderr)
            continue
        if rc != 0:
            print(_blocked_message(cmd), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
