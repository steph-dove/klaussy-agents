"""Tests for the Claude Code plugin manifest under `.claude-plugin/`.

Three separate breakages motivated these, all of which shipped silently because
nothing outside the manifest ever read it:

- The PyPI distribution is `klaussy-agents`. `klaussy` (the CLI command) and
  `klaussy-mcp` (the MCP console script) are not packages, so every install
  instruction naming them 404s.
- `plugin.json` declared `pipx run klaussy-mcp`, which is that 404 — the plugin
  could never start its own MCP server on a machine without klaussy already
  installed.
- `plugin.json`'s `version` drifted to 0.11.0 while the package reached 0.30.4.
  Claude Code pins a plugin to that string, so installed users stop receiving
  updates until it changes.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import tomllib

from klaussy import __version__

REPO = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO / ".claude-plugin"
LAUNCHER = REPO / "scripts" / "klaussy_mcp_launcher.py"

# The one installable name. Anything else in an install command is a 404.
DISTRIBUTION = "klaussy-agents"


def _plugin_json() -> dict:
    return json.loads((PLUGIN_DIR / "plugin.json").read_text())


def _marketplace_json() -> dict:
    return json.loads((PLUGIN_DIR / "marketplace.json").read_text())


def _pyproject_version() -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    return data["project"]["version"]


# --- version drift -----------------------------------------------------------


def test_plugin_version_matches_package_version():
    # Claude Code pins the plugin to plugin.json's `version`: push new commits
    # without changing it and existing users keep the cached copy. A release
    # that bumps pyproject and forgets this file ships an update nobody gets.
    assert _plugin_json()["version"] == _pyproject_version() == __version__


def test_marketplace_entry_does_not_declare_its_own_version():
    # plugin.json always wins over the marketplace entry, silently. Declaring
    # the version in both is how one of them goes stale without anyone noticing.
    entries = _marketplace_json()["plugins"]
    assert entries, "marketplace lists no plugins"
    for entry in entries:
        assert "version" not in entry, f"{entry['name']} duplicates the version"


# --- package naming ----------------------------------------------------------


def _install_commands(text: str) -> list[str]:
    """Every pip/pipx/uv/uvx invocation that names a package to install."""
    pattern = r"(?:pipx (?:install|upgrade|run)|uv tool install|uvx|pip install)[^\n`]*"
    return re.findall(pattern, text)


@pytest.mark.parametrize(
    "path",
    [
        REPO / "skills" / "klaussy-init" / "SKILL.md",
        REPO / "skills" / "klaussy-update" / "SKILL.md",
        REPO / "README.md",
        REPO / "SECURITY.md",
    ],
    ids=lambda p: p.name if p.parent.name == REPO.name else f"{p.parent.name}/{p.name}",
)
def test_install_instructions_name_the_real_distribution(path):
    for command in _install_commands(path.read_text()):
        # Only judge commands that install klaussy itself; the docs also show
        # `pip install requests`-style examples for the dependency guard.
        if "klaussy" not in command:
            continue
        if "klaussy-repo-conventions" in command:
            continue
        assert DISTRIBUTION in command, (
            f"{path.name}: {command!r} installs a package that does not exist on PyPI "
            f"(use {DISTRIBUTION!r})"
        )


# --- MCP server bootstrap ----------------------------------------------------


def test_plugin_mcp_server_runs_the_launcher():
    server = _plugin_json()["mcpServers"]["klaussy"]
    args = server["args"]
    assert any("klaussy_mcp_launcher.py" in arg for arg in args), (
        "plugin.json must bootstrap through the launcher; a bare runner cannot "
        "fall back when the user has neither uvx nor pipx"
    )
    # ${CLAUDE_PLUGIN_ROOT} is what makes the path resolve from the installed
    # checkout rather than the user's cwd.
    assert any("${CLAUDE_PLUGIN_ROOT}" in arg for arg in args)


def test_launcher_referenced_by_plugin_json_exists():
    args = _plugin_json()["mcpServers"]["klaussy"]["args"]
    relative = next(a for a in args if "klaussy_mcp_launcher.py" in a)
    resolved = REPO / relative.replace("${CLAUDE_PLUGIN_ROOT}/", "")
    assert resolved.is_file(), f"{resolved} is missing"
    assert resolved == LAUNCHER


def test_launcher_installs_the_distribution_with_the_mcp_extra():
    # Loaded by path: scripts/ ships with the plugin, not the wheel, so it is
    # not importable by name in every install layout.
    spec = importlib.util.spec_from_file_location("_klaussy_mcp_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Without the extra, `klaussy-mcp` installs but dies importing mcp.server.fastmcp.
    assert module.SPEC == f"{DISTRIBUTION}[mcp]"


def test_mcp_extra_exists_in_pyproject():
    # The launcher's SPEC is only valid while this extra is actually declared.
    extras = tomllib.loads((REPO / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert "mcp" in extras


def test_mcp_server_import_failure_names_the_extra():
    # A bare ModuleNotFoundError reaches the MCP client as nothing but a closed
    # connection, which is unactionable. The guard must print the install fix.
    source = (REPO / "src" / "klaussy" / "mcp_server.py").read_text()
    guard = source.split("from klaussy.toolkit", 1)[0]
    assert "ModuleNotFoundError" in guard
    assert f"{DISTRIBUTION}[mcp]" in guard
