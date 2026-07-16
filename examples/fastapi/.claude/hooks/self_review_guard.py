#!/usr/bin/env python3
"""Cross-agent self-review stop hook: one review pass before the agent finishes.

Wired to each agent's completion/stop event — the point where the model is about
to end its turn. The event name and the field that re-drives the model differ per
agent; all were confirmed from each agent's primary docs:

  * Claude Code   Stop         -> {"decision": "block",  "reason": ...}
  * Codex CLI     Stop         -> {"decision": "block",  "reason": ...}
  * GitHub Copilot agentStop   -> {"decision": "block",  "reason": ...}
  * Gemini CLI    AfterAgent   -> {"decision": "deny",   "reason": ...}
  * Cursor        stop         -> {"followup_message": ...}   (native loop_limit)

opencode's session.idle is handled in its Bun plugin, not this script. Cline's
completion hook (TaskComplete) is observe-only — its stdout isn't read for control
and injected context only reaches the *next* request, so it can't re-drive the
model on stop — and aider has no hook mechanism; users of both get the same pass
via the {{REPO}}-self-review skill instead.

On stop, if the working tree has uncommitted CODE changes, the guard asks the model
to run one self-review pass before finishing. It returns the agent's "re-drive the
model" field with the review directive as its text.

Loop-safe by two independent guards: it honors each agent's native loop signal
(`stop_hook_active` / `loop_count`) as a fast allow, and it fires at most once per
(session, HEAD) via a marker file — so the block -> review -> stop cycle can't
recur, and a commit (which advances HEAD) re-arms it for the next batch of work.

Hardened to never crash or wedge the agent: any unexpected payload or error prints
nothing and exits 0 (allow the stop). Pure stdlib so the repo stays portable.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile

# Baked in by klaussy at scaffold time — selects the output dialect below.
DIALECT: str = 'claude'

# The review pass requested on stop — static, so it's inlined rather than baked.
# Mirrors the {{REPO}}-self-review skill's checklist.
DIRECTIVE = (
    "Before you finish, do one self-review pass over your uncommitted changes. "
    "Start with comments: delete every one that narrates the change or restates what "
    "the code already says, and cut whatever survives to a single sentence. Keep a "
    "comment only where it states something the code cannot — a constraint, a "
    "non-obvious trade-off, a bug being worked around. Deleting is the default; "
    "keeping one needs a reason you could defend in review. Then confirm you reused "
    "existing code instead of reinventing it, preferred the standard library and "
    "existing dependencies over new packages or hand-rolled code, left no dead code "
    "or debug prints, and covered the change with tests that pass. Fix anything that "
    "falls short, then finish. If it already holds, say so briefly and stop."
)

# Source-file suffixes that make a diff worth a review pass. A docs/config-only
# change doesn't trigger the nudge.
CODE_EXTS = (
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".vue",
    ".svelte",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".swift",
    ".scala",
    ".sh",
    ".sql",
)


def _payload() -> dict:
    try:
        _raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        data = json.loads(_raw.decode("utf-8", "replace") if isinstance(_raw, bytes) else _raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _session_id(payload: dict) -> str:
    for key in ("session_id", "sessionId", "conversation_id"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return "nosession"


def _native_loop_allow(payload: dict) -> bool:
    """True if the agent's own loop signal says we've already fired this turn."""
    if payload.get("stop_hook_active") is True:
        return True
    loop_count = payload.get("loop_count")
    return isinstance(loop_count, int) and loop_count > 0


def _git(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def _has_uncommitted_code() -> bool:
    """True if unstaged or staged changes touch a source file."""
    files: set[str] = set()
    for extra in (["--name-only"], ["--name-only", "--cached"]):
        out = _git(["diff", *extra])
        if out:
            files.update(line for line in out.splitlines() if line)
    return any(f.lower().endswith(CODE_EXTS) for f in files)


def _head() -> str:
    out = _git(["rev-parse", "HEAD"])
    return out.strip() if out else "nohead"


def _already_fired(session: str, head: str) -> bool:
    """Marker check keyed by (session, HEAD): fire at most once per episode.

    Best-effort — a filesystem hiccup falls back to firing (safe; the native loop
    guard still prevents an infinite cycle on agents that report one)."""
    key = hashlib.sha1(f"{session}-{head}".encode()).hexdigest()[:16]
    marker = os.path.join(tempfile.gettempdir(), "klaussy-self-review", key)
    try:
        if os.path.exists(marker):
            return True
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as fh:
            fh.write("")
    except OSError:
        return False
    return False


def _emit(dialect: str) -> dict | None:
    """Dialect-specific stop-hook output that re-drives the model with DIRECTIVE."""
    if dialect in ("claude", "codex", "copilot"):
        return {"decision": "block", "reason": DIRECTIVE}
    if dialect == "gemini":
        return {"decision": "deny", "reason": DIRECTIVE}
    if dialect == "cursor":
        return {"followup_message": DIRECTIVE}
    return None


def main() -> int:
    try:
        payload = _payload()
        if _native_loop_allow(payload):
            return 0
        if not _has_uncommitted_code():
            return 0
        if _already_fired(_session_id(payload), _head()):
            return 0
        out = _emit(DIALECT)
        if out is not None:
            print(json.dumps(out))
    except Exception as exc:  # never wedge the agent — allowing the stop is safe
        print(f"klaussy self-review: skipping ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
