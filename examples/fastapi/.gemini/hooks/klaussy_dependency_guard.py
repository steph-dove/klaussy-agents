#!/usr/bin/env python3
"""Cross-agent pre-shell guard: a speed bump before adding a new dependency.

Installed by klaussy into a target agent's hooks directory and wired to that
agent's "before shell/tool" event (Gemini BeforeTool, Cursor
beforeShellExecution, Codex PreToolUse, Copilot preToolUse, Antigravity
run_command, Cline PreToolUse). Agents reach for a new package readily — a whole
HTTP client for one request, lodash for a one-line helper, a second library that
duplicates one already vendored. The guard catches package-manager commands that
ADD a *new named* dependency (`pip install requests`, `npm install lodash`,
`poetry add x`, `cargo add y`, …) and blocks once, asking the agent to confirm
the dep is actually needed and not coverable by the stdlib or an existing dep.

It deliberately does NOT fire on commands that merely sync an existing manifest
(`npm install` / `npm ci`, `pip install -r requirements.txt`, `pip install -e .`,
`poetry install`, `uv sync`, a bare `yarn`) — those add nothing new.

Like the other cross-agent guards, these protocols can't surface a soft warning,
so the mechanism is a block (exit 2 + stderr, honored by every supported agent).
To proceed once confirmed, the agent re-runs the command prefixed with
`KLAUSSY_DEPS_OK=1` — a stateless, self-documenting bypass the guard detects in
the command string itself.

Hardened to never crash: any unexpected payload or error exits 0 (allow), since
some agents (e.g. Copilot preToolUse) treat a crashing hook as a deny of every
tool call. Pure stdlib so the repo stays portable.
"""

from __future__ import annotations

import json
import shlex
import sys

# Prefix the agent adds to a confirmed install to wave it through. Detected as a
# substring of the command, so it survives the stateless per-call hook model.
BYPASS_PREFIX = "KLAUSSY_DEPS_OK=1"

# (manager, verb) pairs whose positional arguments are *new* named dependencies.
# Bare forms with no positional (e.g. `npm install`, `pnpm i`) add nothing and
# fall through to allow — see _packages_after.
_ADDERS = {
    ("npm", "install"),
    ("npm", "i"),
    ("npm", "add"),
    ("pnpm", "install"),
    ("pnpm", "i"),
    ("pnpm", "add"),
    ("yarn", "add"),
    ("bun", "add"),
    ("pip", "install"),
    ("pip3", "install"),
    ("uv", "add"),
    ("poetry", "add"),
    ("cargo", "add"),
    ("gem", "install"),
    ("go", "get"),
}

# Flags that consume the following token as a path/target, not a new named dep
# (`pip install -r reqs.txt`, `pip install -e .`, `-c constraints.txt`).
_FLAGS_WITH_VALUE = {"-r", "--requirement", "-c", "--constraint", "-e", "--editable"}


def _extract_command(payload: dict) -> str:
    """Pull the shell command string out of any supported agent's payload."""
    for container_key in ("tool_input", "toolArgs", "input"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            value = container.get("command")
            if isinstance(value, str) and value:
                return value
        elif isinstance(container, str) and container:
            return container
    top = payload.get("command")
    if isinstance(top, str):
        return top
    return ""


def _packages_after(args: list[str]) -> list[str]:
    """Positional package names among a verb's arguments (flags/paths excluded)."""
    pkgs: list[str] = []
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        if tok in _FLAGS_WITH_VALUE:
            skip_next = True
            continue
        if tok.startswith("-"):
            continue
        # Current project / requirement or lock files / local paths — not a new
        # named dependency, just a sync of what's already declared.
        if tok == "." or tok.endswith((".txt", ".cfg", ".toml")):
            continue
        if tok.startswith(("./", "../", "/")):
            continue
        pkgs.append(tok)
    return pkgs


def _added_packages(command: str) -> list[str]:
    """New named dependencies an install command would add; [] if it adds none."""
    if BYPASS_PREFIX in command:
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    for i in range(len(tokens) - 1):
        mgr, verb = tokens[i], tokens[i + 1]
        # `uv pip install <pkg>` mirrors pip's argument shape.
        if mgr == "uv" and verb == "pip" and i + 2 < len(tokens) and tokens[i + 2] == "install":
            return _packages_after(tokens[i + 3 :])
        if (mgr, verb) in _ADDERS:
            return _packages_after(tokens[i + 2 :])
    return []


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        command = _extract_command(payload)
        packages = _added_packages(command)
        if not packages:
            return 0
        names = ", ".join(packages)
        print(
            f"klaussy dependency gate: this command adds a new dependency ({names}). "
            "Confirm it's actually needed and can't be covered by the standard "
            "library or a package already in the manifest. If it is needed, re-run "
            f"the command prefixed with `{BYPASS_PREFIX}` to proceed, e.g.:\n"
            f"  {BYPASS_PREFIX} {command}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # never crash — see module docstring
        print(f"klaussy dependency gate error (allowing): {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
