"""Resolve whatever directory klaussy was pointed at to the repository it belongs to.

The skill namespace is the repository's folder name (`myapp-review`) and the
scaffolded files belong at its root, so neither may come from the directory the
command happened to run in.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_root(path: Path | str) -> Path | None:
    """The work tree root containing `path`, or None when it isn't in a repo."""
    path = Path(path)
    if not path.exists():
        return None
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip()).resolve()


def resolve_repo(path: Path | str = ".") -> Path:
    """The repository root for `path`, falling back to `path` outside a repo."""
    return git_root(path) or Path(path).resolve()
