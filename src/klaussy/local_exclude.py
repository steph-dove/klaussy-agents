# Copyright 2026 Dovatech LLC. SPDX-License-Identifier: FSL-1.1-MIT
"""`klaussy init --local`: keep the scaffolding out of `git status` for one clone.

The paths klaussy created go into `.git/info/exclude`, which works like
`.gitignore` but is never committed, so teammates and CI never see it.

What klaussy created is read off `git status` before and after the run rather
than recorded by each writer, so a new writer can't forget to report itself.

Git can't exclude changes to a committed file, so a committed file klaussy
edited is put back. Claude's `.claude/settings.json` is the exception: its
additions move to `.claude/settings.local.json`, which Claude Code reads and
treats as personal.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from klaussy.gitignore import GITIGNORE_ENTRIES

BLOCK_START = "# >>> klaussy (local): created by `klaussy init --local`"
BLOCK_END = "# <<< klaussy (local)"
CLAUDE_SETTINGS = ".claude/settings.json"
CLAUDE_LOCAL_SETTINGS = ".claude/settings.local.json"


class NotAGitRepo(Exception):
    """`--local` needs a git repository to keep the exclude file in."""


@dataclass(frozen=True)
class Entry:
    """One `git status` line: whether the path is tracked, and its content."""

    tracked: bool
    digest: str | None
    content: bytes | None


@dataclass
class LocalResult:
    """What `--local` did, for the CLI to report."""

    excluded: list[str] = field(default_factory=list)
    moved_to_local: list[str] = field(default_factory=list)
    # Committed files put back, with why klaussy's change couldn't be kept elsewhere.
    restored: list[tuple[str, str | None]] = field(default_factory=list)
    # Committed files that couldn't be put back, with git's reason.
    failed: list[tuple[str, str]] = field(default_factory=list)


def _git(top: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(top), *args], capture_output=True)


def toplevel(repo: Path) -> Path:
    """The work tree root for `repo`, or NotAGitRepo."""
    proc = _git(repo, "rev-parse", "--show-toplevel")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise NotAGitRepo(str(repo))
    return Path(proc.stdout.decode().strip()).resolve()


def exclude_file(top: Path) -> Path:
    """The clone's `info/exclude`, shared by all of its worktrees."""
    proc = _git(top, "rev-parse", "--git-path", "info/exclude")
    if proc.returncode != 0:
        raise NotAGitRepo(str(top))
    path = Path(proc.stdout.decode().strip())
    return path if path.is_absolute() else (top / path).resolve()


def snapshot(top: Path) -> dict[str, Entry]:
    """Every path `git status` reports, keyed by its repo-relative path."""
    proc = _git(top, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if proc.returncode != 0:
        raise NotAGitRepo(str(top))
    fields = proc.stdout.decode(errors="surrogateescape").split("\0")
    entries: dict[str, Entry] = {}
    i = 0
    while i < len(fields):
        record = fields[i]
        i += 1
        if len(record) < 4:
            continue
        code, rel = record[:2], record[3:]
        if code[0] in "RC":
            i += 1  # the rename source follows as its own field
        path = top / rel
        content = path.read_bytes() if path.is_file() else None
        digest = hashlib.sha256(content).hexdigest() if content is not None else None
        tracked = code != "??"
        entries[rel] = Entry(tracked=tracked, digest=digest, content=content if tracked else None)
    return entries


def _changed(before: dict[str, Entry], after: dict[str, Entry], *, tracked: bool) -> list[str]:
    """Paths the run created or rewrote, tracked or untracked."""
    out = []
    for rel, entry in after.items():
        if entry.tracked != tracked:
            continue
        prior = before.get(rel)
        if prior is None or prior.digest != entry.digest:
            out.append(rel)
    return sorted(out)


def _added(old: object, new: object) -> object:
    """What `new` has that `old` doesn't: new keys, new list items, changed values."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = {}
        for key, val in new.items():
            if key not in old:
                out[key] = val
                continue
            diff = _added(old[key], val)
            if diff not in (None, {}, []):
                out[key] = diff
        return out
    if isinstance(old, list) and isinstance(new, list):
        return [item for item in new if item not in old]
    return None if old == new else new


def _merge(base: object, extra: object) -> object:
    """`extra` folded into `base` without duplicating list items."""
    if isinstance(base, dict) and isinstance(extra, dict):
        out = dict(base)
        for key, val in extra.items():
            out[key] = _merge(out[key], val) if key in out else val
        return out
    if isinstance(base, list) and isinstance(extra, list):
        return base + [item for item in extra if item not in base]
    return base


def _restore(top: Path, rel: str, before: dict[str, Entry]) -> str | None:
    """Put a committed file back as it was before the run. Returns git's error, if any."""
    prior = before.get(rel)
    if prior is not None and prior.content is not None:
        (top / rel).write_bytes(prior.content)
        return None
    proc = _git(top, "checkout", "--", rel)
    if proc.returncode != 0:
        error = proc.stderr.decode(errors="replace").strip()
        return error or f"git checkout exited {proc.returncode}"
    return None


def _move_claude_settings(top: Path, before: dict[str, Entry]) -> str | None:
    """Move klaussy's additions from settings.json to settings.local.json.

    Returns None on success, otherwise why it couldn't, and leaves both files untouched.
    """
    settings = top / CLAUDE_SETTINGS
    prior = before.get(CLAUDE_SETTINGS)
    if prior is not None and prior.content is not None:
        old_text = prior.content.decode()
    else:
        shown = _git(top, "show", f":{CLAUDE_SETTINGS}")
        if shown.returncode != 0:
            return f"couldn't read the committed {CLAUDE_SETTINGS}"
        old_text = shown.stdout.decode()
    try:
        added = _added(json.loads(old_text), json.loads(settings.read_text()))
    except (json.JSONDecodeError, ValueError):
        return f"{CLAUDE_SETTINGS} isn't valid JSON"
    local = top / CLAUDE_LOCAL_SETTINGS
    try:
        existing = json.loads(local.read_text()) if local.is_file() else {}
    except (json.JSONDecodeError, ValueError):
        return f"{CLAUDE_LOCAL_SETTINGS} isn't valid JSON; fix it and run init again"
    if added:
        local.write_text(json.dumps(_merge(existing, added), indent=2) + "\n")
    settings.write_text(old_text)
    return None


def _escape(rel: str) -> str:
    """An exact-path ignore pattern for `rel`, anchored at the repo root."""
    for char in "\\*?[":
        rel = rel.replace(char, "\\" + char)
    return "/" + rel


def _read_block(text: str) -> tuple[list[str], list[str]]:
    """The klaussy block's patterns, and every line outside it."""
    inside, outside, in_block = [], [], False
    for line in text.splitlines():
        if line == BLOCK_START:
            in_block = True
        elif line == BLOCK_END:
            in_block = False
        elif in_block:
            inside.append(line)
        else:
            outside.append(line)
    return inside, outside


def has_block(top: Path) -> bool:
    path = exclude_file(top)
    return path.is_file() and BLOCK_START in path.read_text()


def write_block(top: Path, patterns: list[str]) -> None:
    """Replace the klaussy block in the exclude file, keeping everything else."""
    path = exclude_file(top)
    _, outside = _read_block(path.read_text() if path.is_file() else "")
    while outside and not outside[-1].strip():
        outside.pop()
    lines = [*outside, "", BLOCK_START, *patterns, BLOCK_END] if outside else [
        BLOCK_START,
        *patterns,
        BLOCK_END,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def remove_block(top: Path) -> bool:
    """Drop the klaussy block. True when there was one."""
    path = exclude_file(top)
    if not path.is_file():
        return False
    text = path.read_text()
    if BLOCK_START not in text:
        return False
    _, outside = _read_block(text)
    while outside and not outside[-1].strip():
        outside.pop()
    path.write_text("\n".join(outside) + "\n" if outside else "")
    return True


def apply(top: Path, before: dict[str, Entry]) -> LocalResult:
    """Exclude what the run created and undo its edits to committed files."""
    result = LocalResult()
    after = snapshot(top)

    for rel in _changed(before, after, tracked=True):
        why = None
        if rel == CLAUDE_SETTINGS:
            why = _move_claude_settings(top, before)
            if why is None:
                result.moved_to_local.append(rel)
                continue
        error = _restore(top, rel, before)
        if error:
            result.failed.append((rel, error))
        else:
            result.restored.append((rel, why))

    created = set(_changed(before, snapshot(top), tracked=False))
    path = exclude_file(top)
    previous, _ = _read_block(path.read_text() if path.is_file() else "")
    for pattern in previous:
        rel = pattern[1:].replace("\\", "") if pattern.startswith("/") else None
        if rel and (top / rel).exists():
            created.add(rel)

    result.excluded = sorted(created)
    patterns = [_escape(rel) for rel in result.excluded]
    patterns += [entry for entry in GITIGNORE_ENTRIES if not entry.startswith("#")]
    write_block(top, patterns)
    return result
