"""Fast, dependency-light launcher for klaussy's hook guards."""

import os
import runpy
import subprocess
import sys


def _resolve_in_repo(relpath: str) -> str | None:
    """Resolve a repo-relative guard path against the enclosing git root."""
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


def _run(script: str) -> int:
    """Execute a guard, propagating its exit code and failing open on anything else."""
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except Exception:
        return 0
    return 0


def _run_packaged(name: str, extra: list[str]) -> int:
    """Run a guard shipped inside the installed klaussy package."""
    try:
        from importlib import resources

        ref = resources.files("klaussy").joinpath(f"templates/hooks/{os.path.basename(name)}")
        with resources.as_file(ref) as path:
            sys.argv = [str(path), *extra]
            return _run(str(path))
    except Exception:
        return 0


def main() -> int:
    """Run the guard named in argv[1], propagating its exit code."""
    if len(sys.argv) < 2:
        return 0
    if sys.argv[1] == "--packaged":
        if len(sys.argv) < 3:
            return 0
        return _run_packaged(sys.argv[2], sys.argv[3:])
    if sys.argv[1] == "--repo-relative":
        if len(sys.argv) < 3:
            return 0
        resolved = _resolve_in_repo(sys.argv[2])
        if resolved is None:
            return 0
        sys.argv = [sys.argv[0], resolved, *sys.argv[3:]]
    script = sys.argv[1]
    sys.argv = [script, *sys.argv[2:]]
    return _run(script)
