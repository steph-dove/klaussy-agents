#!/usr/bin/env python3
"""Cross-agent pre-shell guard: run format + lint before a `git commit`.

Installed by klaussy into a target agent's hooks directory and wired to that
agent's "before shell/tool" event (Gemini BeforeTool, Cursor
beforeShellExecution, Codex PreToolUse, Copilot preToolUse). The guard pulls the
shell command out of the hook payload — whose shape differs per agent — checks
whether it's a `git commit`, and if so runs the project's format and lint
commands. A non-zero exit blocks the commit (exit code 2 + stderr is honored as
a block by all supported agents) and surfaces the failing command back.

Commands carrying the `__KLAUSSY_PATHS__` placeholder are scoped to the files
being committed, so the gate judges only the change in flight — not pre-existing
issues elsewhere in the tree. Commands without it (e.g. a project's own
`npm run lint` script) run repo-wide as written.

Hardened to never crash: any unexpected payload or error exits 0 (allow). This
matters because some agents (e.g. Copilot preToolUse) treat a crashing hook as a
*deny of every tool call*. Pure stdlib so the repo stays portable.

Format/lint commands are baked in at scaffold time. Edit this file (or re-run
`klaussy hooks --force --agents <agent>`) to change them.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# Sentinels replaced by klaussy at scaffold time. Any may be None.
FORMAT_CMD: str | None = "__KLAUSSY_FORMAT_CMD__"
LINT_CMD: str | None = "__KLAUSSY_LINT_CMD__"
# Deterministic commented-out-code check (block-only; flags, never deletes).
COMMENT_CHECK_CMD: str | None = "__KLAUSSY_COMMENT_CHECK_CMD__"
# Deterministic verbose-comment check (block-only literal, no sentinel).
# `--diff` scopes it to lines changed vs HEAD so pre-existing comments
# elsewhere in a touched file don't block the commit.
VERBOSE_COMMENT_CMD: str | None = "klaussy comment-lint --diff __KLAUSSY_PATHS__"

# Stand-in for the files being committed; expanded just before each command runs.
PATHS_TOKEN = "__KLAUSSY_PATHS__"

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

# Matches `git commit` / `git -C path commit`, not `git commitlint` or a quoted
# string that merely mentions commit.
GIT_COMMIT_RE = re.compile(r"(^|[\s;&|])git(\s+-[^\s]+\s+\S+)*\s+commit(\s|$)")


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
    """True for `git commit -a`/--all, whose files aren't staged yet when this
    hook fires — so the staged-paths lookup must include working-tree changes."""
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
    """Run a check, inheriting its stdout/stderr so its own output is the record.

    A missing or unparseable command can't judge the diff, so it allows the
    commit silently rather than block — and without printing, to keep the guard
    quiet on every commit (verbose per-command chatter floods an agent's
    context, especially with many staged files)."""
    try:
        return subprocess.run(shlex.split(cmd)).returncode
    except (OSError, ValueError):
        return 0


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
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        command = _extract_command(payload)
        if not _is_git_commit(command):
            return 0
        if _skips_verify(command):
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
                print(_blocked_message(cmd), file=sys.stderr)
                return 2
        return 0
    except Exception as exc:  # never crash — see module docstring
        print(f"klaussy pre-commit guard error (allowing): {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
