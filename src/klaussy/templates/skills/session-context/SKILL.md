---
name: {{SKILL_PREFIX}}-session-context
description: Use when reading, writing, listing, or managing uncommitted Open Knowledge Format (OKF) session notes for active multi-agent coordination across worktrees in klaussy-desktop.
---

## Target

`$ARGUMENTS`

Supported operations:
- `read` / `list`: Read active OKF session context notes for the current session.
- `write` / `add`: Create an uncommitted session note for other agents to read.
- `clear`: Clear session context notes for the active session.

## Environment Variables

- `$KLAUSSY_SESSION_ID`: Active session ID string.
- `$KLAUSSY_SESSION_NOTES_DIR`: Absolute directory path to uncommitted session notes (`.git/klaussy-session/notes/<sessionId>` or `~/.klaussy/sessions/<sessionId>/notes/`).

## Instructions

1. **When Reading Session Context:**
   - Check if `$KLAUSSY_SESSION_NOTES_DIR` exists or locate `.git/klaussy-session/notes/$KLAUSSY_SESSION_ID/` in the worktree.
   - Read all Markdown (`.md`) files in that directory.
   - Inspect frontmatter metadata (`agent`, `provider`, `affected_files`, `tags`, `timestamp`) and note contents to learn about active work done by other agents in concurrent worktrees.

2. **When Writing a Session Note:**
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
   - Save the file to `$KLAUSSY_SESSION_NOTES_DIR/note-<timestamp>.md`.

3. **Git Safety Rule:**
   - NEVER stage or commit `$KLAUSSY_SESSION_NOTES_DIR` or `.git/klaussy-session/` into Git.
   - Session context notes are strictly uncommitted runtime state.
