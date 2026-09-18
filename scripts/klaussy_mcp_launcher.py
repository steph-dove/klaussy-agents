#!/usr/bin/env python3
"""Bootstrap `klaussy-mcp` for the Claude Code plugin.

A plugin ships as a git checkout, not a Python install, so the MCP server it
declares has to find its own runtime on a machine that may have nothing
installed. `.claude-plugin/plugin.json` points at this script rather than at a
single hardcoded runner, and it walks the same uvx/pipx fallback chain
`claude_md.py` uses for klaussy-repo-conventions.

Order matters:

1. The current interpreter, but only when it can import *both* `klaussy` and
   `mcp` — that is the editable-install case, where reaching for PyPI would
   silently shadow the developer's working tree with the published release.
2. `uvx`, then `pipx`, against the real distribution name with the extra:
   `klaussy-agents[mcp]`. The distribution is `klaussy-agents`; `klaussy` and
   `klaussy-mcp` are not packages on PyPI and resolve to a 404.

Exec rather than spawn so the child owns stdin/stdout directly — MCP speaks
JSON-RPC over stdio and a relaying parent would only add a place to lose bytes.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys

# The PyPI distribution plus the optional extra that provides `mcp.server.fastmcp`.
# `klaussy-mcp` is the console script's name, not an installable package.
SPEC = "klaussy-agents[mcp]"


def _can_serve_in_process() -> bool:
    """True when this interpreter already has klaussy *and* the mcp extra."""
    try:
        return all(
            importlib.util.find_spec(mod) is not None
            for mod in ("klaussy.mcp_server", "mcp.server.fastmcp")
        )
    except (ImportError, ValueError):
        # A namespace-package or partially-installed parent raises rather than
        # returning None. Treat it as "not usable" and fall through to a runner.
        return False


def main() -> None:
    if _can_serve_in_process():
        os.execv(sys.executable, [sys.executable, "-m", "klaussy.mcp_server"])

    for runner, args in (
        ("uvx", ["--from", SPEC, "klaussy-mcp"]),
        ("pipx", ["run", "--spec", SPEC, "klaussy-mcp"]),
    ):
        path = shutil.which(runner)
        if path:
            os.execv(path, [runner, *args])

    sys.exit(
        "klaussy-mcp could not start: no runtime found.\n"
        "Install one of these, then restart the MCP client:\n"
        f"  uv:   uv tool install '{SPEC}'      (or just have `uvx` on PATH)\n"
        f"  pipx: pipx install '{SPEC}'\n"
        f"  pip:  pip install '{SPEC}'"
    )


if __name__ == "__main__":
    main()
