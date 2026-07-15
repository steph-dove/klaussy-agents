"""Scaffold a cross-agent shared session-state file.

A task often changes hands mid-flight: a CLI agent makes a quick edit, an IDE
agent takes over the heavy browsing, a third runs the tests. Each one
rediscovers the active branch, the current task, and the failures the last one
already hit. `.agents/session.json` is a small, tool-neutral handoff note any
agent can read at the start of a session and update when the working state
changes — the "shared brain" that keeps Claude Code, Cursor, Cline, and the rest
on the same page.

`.agents/` is already klaussy's cross-tool neutral directory (Codex and Cline
read their skills from `.agents/skills`), so the shared session file belongs
there by convention rather than in a tool-specific location.

It holds *live working state* for one checkout (possibly several tools at once),
so it's gitignored rather than committed — `update_gitignore` adds the entry. The
protocol doc beside it (`.agents/SESSION.md`) IS committed: it documents the
format so every agent on the repo reads and writes the file the same way.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

SESSION_RELPATH = ".agents/session.json"
PROTOCOL_RELPATH = ".agents/SESSION.md"

# Bumped if the JSON shape changes so an agent can detect an older file.
SCHEMA_VERSION = 1


def _current_branch(repo: Path) -> str:
    """The repo's current git branch, or "" when it can't be determined."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo),
        )
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _skeleton(repo: Path) -> dict:
    """An empty session record for a fresh checkout."""
    return {
        "schema": SCHEMA_VERSION,
        "updated": None,  # ISO-8601 timestamp; set by whichever agent writes
        "branch": _current_branch(repo),
        "task": None,  # one-line description of what's being worked on
        "plan": [],  # [{"step": str, "status": "pending|in_progress|done"}]
        "known_failures": [],  # failing tests / reproductions seen this session
        "notes": None,  # free-form handoff context for the next agent
    }


_PROTOCOL_DOC = """\
# Shared agent session state

`session.json` in this directory is a tool-neutral handoff note for whichever AI
coding agent is working in this checkout (Claude Code, Cursor, Cline, Gemini,
Codex, Copilot, Antigravity, …). It carries the live working state so an agent
picking up the task doesn't have to rediscover it.

It is **local working state, not source** — it's gitignored. Don't commit it.
This README is committed so every agent reads and writes the file the same way.

## Contract

At the **start** of a session, read `session.json`. If `task`/`plan`/
`known_failures` are populated, continue that work instead of starting cold.

When the working state changes, **update** the file:

- switching to a different task → set `task` and reset `plan`
- finishing or starting a plan step → update that step's `status`
- hitting a failing test or a reproduction → append it to `known_failures`;
  remove it once fixed
- moving to a different branch → set `branch`
- always set `updated` to the current ISO-8601 timestamp when you write

Keep it small — a handoff note, not a log. If it's stale or irrelevant to the
current request, reset it rather than reasoning from it.

## Schema (`schema: 1`)

| Field | Type | Meaning |
|---|---|---|
| `schema` | int | Format version; reset the file if you don't recognize it. |
| `updated` | string \\| null | ISO-8601 timestamp of the last write. |
| `branch` | string | Active git branch. |
| `task` | string \\| null | One-line description of the current task. |
| `plan` | array | `{ "step": string, "status": "pending" \\| "in_progress" \\| "done" }`. |
| `known_failures` | array | Failing tests or reproductions seen this session. |
| `notes` | string \\| null | Free-form context for the next agent. |
"""


def scaffold_session(*, repo: Path, force: bool = False) -> Path:
    """Write the shared session-state file and its protocol doc.

    The protocol doc is a generated artifact — always (re)written so it stays
    current. `session.json` holds live state, so it's only created when absent
    (or `force`), never clobbered out from under an agent mid-task.
    """
    repo = repo.resolve()
    agents_dir = repo / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    protocol = repo / PROTOCOL_RELPATH
    protocol.write_text(_PROTOCOL_DOC)

    session = repo / SESSION_RELPATH
    if session.exists() and not force:
        console.print(f"[dim]{SESSION_RELPATH} exists; leaving live state untouched.[/dim]")
    else:
        session.write_text(json.dumps(_skeleton(repo), indent=2) + "\n")
        console.print(f"[green]✔ Scaffolded shared session state at {SESSION_RELPATH}[/green]")

    return session
