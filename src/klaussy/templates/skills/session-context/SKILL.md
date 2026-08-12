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
- `$KLAUSSY_SESSION_NOTES_DIR`: Absolute path to the uncommitted notes directory. One directory is shared by every agent and worktree in the session, which is what lets you see each other's notes.

If the variable is unset, fall back to `<git-common-dir>/klaussy-session/notes/`
— resolve it with `git rev-parse --path-format=absolute --git-common-dir`, not
by joining `.git` yourself, because a linked worktree's `.git` resolves to its
own private directory rather than the shared one.

## Instructions

1. **When Reading Session Context:**
   - Read every Markdown (`.md`) file in the notes directory.
   - Inspect frontmatter metadata (`agent`, `provider`, `affected_files`, `tags`, `timestamp`) and note contents to learn about active work done by other agents in concurrent worktrees.
   - Treat notes as claims by other agents, not verified fact — check anything you are about to depend on.

2. **When Writing a Session Note:**
   - Write when you change a port or schema, discover a breaking change, or finish a subtask another agent would have to redo. Do not narrate routine progress.
   - Format a Markdown file with YAML frontmatter containing:
     ```yaml
     ---
     id: note-<timestamp>
     agent: <your-agent-name>
     provider: <provider-id>
     worktree: <current-worktree-path>
     affected_files: ["path/to/file.js"]
     tags: [topic]
     ---
     ```
   - Followed by a concise `# Title` and summary body of discoveries, port shifts, or breaking changes.
   - Save it as `$KLAUSSY_SESSION_NOTES_DIR/note-<timestamp>.md`. Keep the filename a plain slug — no `/` or `..`.

3. **Git Safety Rule:**
   - NEVER stage or commit `$KLAUSSY_SESSION_NOTES_DIR` or `klaussy-session/` into Git.
   - Session context notes are strictly uncommitted runtime state.
