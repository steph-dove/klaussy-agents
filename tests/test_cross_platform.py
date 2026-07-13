"""Cross-platform (macOS / Linux / Windows) portability of generated hooks.

These lock the OS-portability decisions so a refactor can't silently regress a
committed config back to a Unix-only form. See the README "Cross-platform"
section for the per-agent support matrix.
"""

import json
import sys
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


def test_gemini_hooks_use_launcher(repo: Path):
    # Gemini has no per-OS command field, so it invokes the klaussy-hook launcher
    # (PATH-resolved on every OS) instead of a frozen python/python3 token.
    from klaussy.agents.backends import GeminiBackend

    GeminiBackend().emit_hooks(repo, force=True)
    settings = json.loads((repo / ".gemini" / "settings.json").read_text())
    commands = [
        h["command"]
        for events in settings.get("hooks", {}).values()
        for entry in events
        for h in entry.get("hooks", [])
    ]
    assert commands
    for c in commands:
        assert c.startswith('klaussy-hook "')
        assert "python3" not in c and "python " not in c


# --- klaussy-hook launcher --------------------------------------------------


def _launch(script: Path, monkeypatch, *extra: str) -> int:
    from klaussy import _hooklauncher

    monkeypatch.setattr(sys, "argv", ["klaussy-hook", str(script), *extra])
    return _hooklauncher.main()


def test_launcher_propagates_block_exit(tmp_path: Path, monkeypatch):
    guard = tmp_path / "g.py"
    guard.write_text("import sys\nsys.exit(2)\n")
    assert _launch(guard, monkeypatch) == 2  # block passes through


def test_launcher_allows_on_zero_exit(tmp_path: Path, monkeypatch):
    guard = tmp_path / "g.py"
    guard.write_text("import sys\nsys.exit(0)\n")
    assert _launch(guard, monkeypatch) == 0


def test_launcher_fails_open_on_broken_guard(tmp_path: Path, monkeypatch):
    # A missing or crashing guard must not block the agent — fail open (0).
    missing = tmp_path / "does_not_exist.py"
    assert _launch(missing, monkeypatch) == 0
    boom = tmp_path / "boom.py"
    boom.write_text("raise RuntimeError('kaboom')\n")
    assert _launch(boom, monkeypatch) == 0


def test_launcher_no_args_allows(monkeypatch):
    from klaussy import _hooklauncher

    monkeypatch.setattr(sys, "argv", ["klaussy-hook"])
    assert _hooklauncher.main() == 0
