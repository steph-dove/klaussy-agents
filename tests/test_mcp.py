"""Tests for the klaussy MCP server (klaussy.mcp_server)."""

import asyncio
import json

from klaussy.mcp_server import klaussy_humanize, klaussy_status, mcp


def _tool_names() -> set[str]:
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def test_one_tool_per_cli_command_plus_status():
    assert _tool_names() == {
        "klaussy_init",
        "klaussy_checklist",
        "klaussy_skills",
        "klaussy_settings",
        "klaussy_hooks",
        "klaussy_github",
        "klaussy_humanize",
        "klaussy_status",
    }


def test_status_reports_every_skill(tmp_path):
    # Regression: the old server kept a stale SKILL_NAMES that omitted
    # precommit/humanize, so klaussy_status never reported them.
    reported = json.loads(klaussy_status(str(tmp_path)))
    assert any("precommit" in key for key in reported)
    assert any("-humanize/" in key for key in reported)


def test_humanize_text_scrubs_inline_without_subprocess():
    out = klaussy_humanize(text="A great solution — it works.")
    assert "—" not in out
    assert out == "A great solution, it works."


def test_humanize_requires_text_or_files():
    assert "Provide" in klaussy_humanize()
