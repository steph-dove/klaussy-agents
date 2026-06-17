"""Multi-agent scaffolding: target backends + selection helpers.

klaussy generates Claude Code boilerplate and translates it into the native
formats of other AI coding agents (Gemini CLI, Cursor, Codex, GitHub Copilot),
all of which now read the open Agent Skills `SKILL.md` spec.
"""

from __future__ import annotations

from klaussy.agents.backends import BACKENDS, ClaudeBackend, GenericBackend

ALL_AGENTS = list(BACKENDS.keys())
# No --agents and no --all → scaffold every supported agent. The bundled skills
# are portable across all five, so the default is "make this repo ready for
# whatever agent the user (or a teammate) reaches for".
DEFAULT_AGENTS = list(ALL_AGENTS)


def resolve_agents(spec: str | None, *, all_agents: bool = False) -> list[str]:
    """Resolve a --agents spec (comma list) / --all flag into ordered keys.

    Preserves registry order, de-duplicates, and validates names. With neither
    a spec nor --all, defaults to every supported agent. Raises ValueError
    listing the unknown names so the CLI can surface a clean error.
    """
    if all_agents:
        return list(ALL_AGENTS)
    if not spec:
        return list(DEFAULT_AGENTS)

    requested = [name.strip().lower() for name in spec.split(",") if name.strip()]
    unknown = [name for name in requested if name not in BACKENDS]
    if unknown:
        raise ValueError(
            f"Unknown agent(s): {', '.join(unknown)}. "
            f"Available: {', '.join(ALL_AGENTS)}."
        )
    # Registry order, de-duplicated.
    return [key for key in ALL_AGENTS if key in set(requested)]


__all__ = [
    "ALL_AGENTS",
    "DEFAULT_AGENTS",
    "BACKENDS",
    "ClaudeBackend",
    "GenericBackend",
    "resolve_agents",
]
