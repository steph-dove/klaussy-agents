---
name: {{REPO}}-session-context
description: Use when reading, writing, listing, or managing uncommitted Open Knowledge Format (OKF) session notes for active multi-agent coordination across worktrees.
allowed-tools: Read Grep Glob Bash Write
---

## Target

`$ARGUMENTS`

Supported operations:
- `read` / `list`: Read active OKF session context notes for the current session.
- `write` / `add`: Create an uncommitted session note for other agents to read.
- `clear`: Clear session context notes for the active session.

## Environment Variables

- `$KLAUSSY_SESSION_ID`: Identifies the terminal you are running in. Stamp it on notes you write; it does NOT scope the notes directory.
- `$KLAUSSY_SESSION_NOTES_DIR`: Absolute path to the notes directory. One directory is shared by every agent and every repo in the session, which is what lets you see each other's notes.

Use the variable exactly as given — do not guess or rebuild the path, and do not
write to a relative path, which some CLIs resolve against their own scratch
directory rather than the repo. If it is unset you are not running in a klaussy
session: skip session notes entirely.

## Instructions

1. **When Reading Session Context:**
   - Read every Markdown (`.md`) file in the notes directory.
   - Inspect frontmatter metadata (`agent`, `provider`, `affected_files`, `tags`, `timestamp`, `stale_after`) and note contents to learn about active work done by other agents in concurrent worktrees.
   - A note whose `stale_after` date has passed is history, not current state; read it, but do not act on it as though it still holds.
   - Treat notes as claims by other agents, not verified fact — check anything you are about to depend on.

2. **When Writing a Session Note:**
   - Write whenever your work leaves something another agent in this session would otherwise discover the hard way: a port or schema that moved, a new required env var or setup step, a service now running elsewhere, a breaking change, or a subtask they would repeat.
   - Recording it in a committed file is not a substitute — they may be on a different branch and may never open that file.
   - Do not narrate routine progress. If nothing you did changes what another agent would do, write nothing.
   - Format a Markdown file with YAML frontmatter containing:
     ```yaml
     ---
     type: session-note
     id: note-<timestamp>
     agent: <your-agent-name>
     provider: <provider-id>
     worktree: <current-worktree-path>
     affected_files: ["path/to/file.js"]
     tags: [topic]
     ---
     ```
   - `type` is the one field the Open Knowledge Format requires; keep it as `session-note` so other OKF tooling can read these.
   - Followed by a concise `# Title` and summary body of discoveries, port shifts, or breaking changes.
   - Save it as `$KLAUSSY_SESSION_NOTES_DIR/note-<timestamp>.md`. Keep the filename a plain slug — no `/` or `..`.

3. **Git Safety Rule:**
   - Notes live outside the repository. Never copy one into the working tree or commit it.
   - Session context notes are strictly runtime state, and they expire.
