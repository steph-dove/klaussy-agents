import subprocess
from pathlib import Path

import pytest

from klaussy import claude_md


def _fake_run(calls):
    """Every install attempt fails; `conventions` writes CLAUDE.md."""

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "conventions":
            (Path(kwargs["cwd"]) / "CLAUDE.md").write_text("# x\n")
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 1)

    return run


def test_init_uses_the_installed_conventions_when_the_upgrade_fails(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(claude_md.subprocess, "run", _fake_run(calls))
    monkeypatch.setattr(claude_md.shutil, "which", lambda name: f"/bin/{name}")
    assert claude_md.run_init(repo=tmp_path, skip_enrich=True) == tmp_path / "CLAUDE.md"
    assert calls[-1][:2] == ["conventions", "discover"]


def test_init_fails_when_conventions_is_neither_installable_nor_installed(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(claude_md.subprocess, "run", _fake_run(calls))
    monkeypatch.setattr(claude_md.shutil, "which", lambda _: None)
    with pytest.raises(SystemExit):
        claude_md.run_init(repo=tmp_path, skip_enrich=True)
    assert all(c[0] != "conventions" for c in calls)


def test_init_falls_back_to_uv_tool_install_then_pipx(tmp_path, monkeypatch):
    calls = []
    run = _fake_run(calls)

    def no_uv(cmd, **kwargs):
        if cmd[0] == "uv":
            calls.append(cmd)
            raise FileNotFoundError(cmd[0])
        return run(cmd, **kwargs)

    monkeypatch.setattr(claude_md.subprocess, "run", no_uv)
    monkeypatch.setattr(claude_md.shutil, "which", lambda name: f"/bin/{name}")
    claude_md.run_init(repo=tmp_path, skip_enrich=True)
    assert calls[1][:3] == ["uv", "tool", "install"]
    assert calls[2][:2] == ["pipx", "install"]
