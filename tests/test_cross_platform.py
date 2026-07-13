"""Cross-platform (macOS / Linux / Windows) portability of generated hooks.

These lock the OS-portability decisions so a refactor can't silently regress a
committed config back to a Unix-only form. See the README "Cross-platform"
section for the per-agent support matrix.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "CLAUDE.md").write_text("# test\n\n## Project Overview\n\nx\n")
    return tmp_path


def test_codex_emits_per_os_command_override(repo: Path):
    # Codex is the one non-Copilot agent with a first-class per-OS override.
    # `command` stays POSIX (python3) and `commandWindows` uses the Windows
    # launcher (py -3); Codex picks per the CONSUMER's OS, so both are hardcoded
    # by target OS rather than by the scaffolding machine.
    from klaussy.agents.backends import CodexBackend

    CodexBackend().emit_hooks(repo, force=True)
    cfg = json.loads((repo / ".codex" / "hooks.json").read_text())

    entries = [h for e in cfg["hooks"]["PreToolUse"] for h in e["hooks"]]
    entries += [h for e in cfg["hooks"]["UserPromptSubmit"] for h in e["hooks"]]
    entries += [h for e in cfg["hooks"]["Stop"] for h in e["hooks"]]
    assert entries  # sanity

    for h in entries:
        assert h["command"].startswith("python3 ")  # POSIX default
        assert h["commandWindows"].startswith("py -3 ")  # Windows override
        # Never emit a bare `python3` on the Windows variant — stock python.org
        # Windows installs don't provide it.
        assert "python3" not in h["commandWindows"]
