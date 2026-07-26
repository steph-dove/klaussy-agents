"""Fast, dependency-light launcher for klaussy's hook guards.

A committed hook command can't portably name a Python interpreter: `python3` is
absent on a stock python.org Windows install, and `python` isn't guaranteed on
Linux/macOS. Agents whose hook config is a single command string (Claude, Gemini)
have no per-OS field to pick the right one, so the interpreter would otherwise be
frozen to whatever machine ran `klaussy init`.

This console script sidesteps that: pip installs it on PATH as `klaussy-hook`
(`klaussy-hook.exe` on Windows), so the hook command is `klaussy-hook "<guard>"`
— interpreter-agnostic and resolvable in every shell on every OS. It runs the
guard under the same interpreter klaussy is installed on. `klaussy` is already a
runtime dependency of the comment/commit guards (they shell out to it), so this
adds nothing new to install.

`--repo-relative <path>` resolves the guard against the enclosing git repo
instead of an absolute path. Kimi Code CLI needs it: its hooks live in the user's
global config, and its four-field `[[hooks]]` schema has no per-OS override or
room for the shell one-liner other backends resolve the repo with.

Kept deliberately import-light (stdlib only, no rich/typer) and in-process (via
runpy, no second interpreter spawn) so it stays cheap enough to run on every
file-read hook.
"""

import os
import runpy
import subprocess
import sys


def _resolve_in_repo(relpath: str) -> str | None:
    """Resolve a repo-relative guard path against the enclosing git root.

    Returns None outside a git repo, which fails the launcher open — the point
    of the flag is that a globally-configured hook stays inert in repos klaussy
    hasn't scaffolded.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return os.path.join(out.stdout.strip(), relpath)


def main() -> int:
    """Run the guard script named in argv[1], propagating its exit code.

    A guard blocks by exiting non-zero (2); it allows by exiting 0 or returning.
    Anything that prevents the guard from running (missing file, import error)
    fails open (exit 0) — a crashing hook can otherwise block every tool call on
    some agents, and the guards themselves already fail open on internal errors.
    """
    if len(sys.argv) < 2:
        return 0
    if sys.argv[1] == "--repo-relative":
        if len(sys.argv) < 3:
            return 0
        resolved = _resolve_in_repo(sys.argv[2])
        if resolved is None:
            return 0
        sys.argv = [sys.argv[0], resolved, *sys.argv[3:]]
    script = sys.argv[1]
    # Present the guard with its own name as argv[0] and any trailing args, so a
    # guard that inspects sys.argv sees what it would under a direct invocation.
    sys.argv = [script, *sys.argv[2:]]
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except Exception:
        return 0
    return 0
