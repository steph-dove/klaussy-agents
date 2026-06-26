#!/usr/bin/env python3
"""Cross-agent pre-plan guidance injector: feed klaussy's guardrails to the agent.

Wired to each agent's earliest "before the model plans" event; coverage differs
because each exposes a different injection surface:

  * Claude Code  PreToolUse(EnterPlanMode)  -> injects the moment plan mode opens
  * Codex        UserPromptSubmit           -> injects only when permission_mode == "plan"
  * Gemini CLI   BeforeAgent                -> injects each turn, before planning
  * Cursor       sessionStart               -> injects once per session
  * Copilot      sessionStart               -> injects once per session
  * Cline        UserPromptSubmit           -> injects each prompt (no plan signal)

Guidance text and DIALECT are baked in at scaffold time, so the script needs no
arguments. Hardened to never crash or block: any unexpected payload or error
prints nothing and exits 0.

Edit GUIDANCE below (or re-run `klaussy hooks --force --agents <agent>`).
"""

from __future__ import annotations

import json
import sys

# Baked in by klaussy at scaffold time.
GUIDANCE: str = "__KLAUSSY_GUIDANCE__"
DIALECT: str = "__KLAUSSY_DIALECT__"


def _payload() -> dict:
    """Read the hook's stdin JSON, tolerating empty or malformed input."""
    try:
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _emit(dialect: str, payload: dict) -> dict | None:
    """Build the dialect-specific stdout object, or None to inject nothing.

    `additionalContext` (camelCase) is the field Claude / Codex / Gemini /
    Copilot read; Cursor uses `additional_context` (snake_case). The wrapping
    object differs too, so each dialect is spelled out rather than guessed.
    """
    if dialect == "claude":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": GUIDANCE,
            }
        }
    if dialect == "codex":
        # The EnterPlanMode matcher gates Claude; Codex has no plan tool, so gate
        # on the permission_mode it reports on stdin instead.
        if payload.get("permission_mode") != "plan":
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": GUIDANCE,
            }
        }
    if dialect == "gemini":
        return {
            "hookSpecificOutput": {
                "hookEventName": "BeforeAgent",
                "additionalContext": GUIDANCE,
            }
        }
    if dialect == "cursor":
        return {"additional_context": GUIDANCE}
    if dialect == "copilot":
        return {"additionalContext": GUIDANCE}
    if dialect == "cline":
        # Cline's UserPromptSubmit uses contextModification and lacks a plan-mode
        # signal, so guidance is injected on every prompt.
        return {"cancel": False, "contextModification": GUIDANCE}
    return None


def main() -> int:
    try:
        out = _emit(DIALECT, _payload())
        if out is not None:
            print(json.dumps(out))
    except Exception as exc:  # never crash — injecting nothing is always safe
        print(f"klaussy plan-guidance: skipping ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
