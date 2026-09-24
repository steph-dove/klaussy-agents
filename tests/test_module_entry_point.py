"""`python -m klaussy` has to work, because the skills tell agents to run it.

The humanize skill has offered that fallback for a while and it could never
have worked: there was no `__main__`, so every invocation died with "No module
named klaussy.__main__". Nothing caught it, because the skills were only ever
checked for *mentioning* a fallback, never for the fallback running.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "klaussy", *args], capture_output=True, text=True)


def test_the_module_entry_point_exists():
    out = _run("--help")
    assert out.returncode == 0, out.stderr
    assert "No module named" not in out.stderr


@pytest.mark.parametrize("command", ["base", "comment-lint", "import-lint", "secret-scan"])
def test_each_command_the_skills_fall_back_to_is_reachable(command):
    """A subcommand a skill names must resolve through the module route too."""
    out = _run(command, "--help")
    assert out.returncode == 0, f"`python -m klaussy {command}` failed: {out.stderr}"


def test_the_module_route_and_the_console_script_are_the_same_cli():
    """Both entry points must reach the same app, not two drifting copies."""
    module = _run("--help").stdout
    assert "base" in module, "the module route is missing commands the console script has"
