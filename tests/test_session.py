"""Tests for the cross-agent shared session-state scaffolder."""

import json
import subprocess
from pathlib import Path

from klaussy import toolkit
from klaussy.gitignore import GITIGNORE_ENTRIES, update_gitignore
from klaussy.session import (
    PROTOCOL_RELPATH,
    SCHEMA_VERSION,
    SESSION_RELPATH,
    scaffold_session,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def test_scaffolds_session_and_protocol(tmp_path: Path):
    scaffold_session(repo=tmp_path)
    session = tmp_path / SESSION_RELPATH
    protocol = tmp_path / PROTOCOL_RELPATH
    assert session.exists() and protocol.exists()

    data = json.loads(session.read_text())
    assert data["schema"] == SCHEMA_VERSION
    assert data["plan"] == [] and data["known_failures"] == []
    assert data["task"] is None
    assert "Shared agent session state" in protocol.read_text()


def test_records_current_branch(tmp_path: Path):
    _git(tmp_path, "init")
    _git(tmp_path, "commit", "--allow-empty", "-m", "init")
    _git(tmp_path, "checkout", "-b", "feature/x")
    scaffold_session(repo=tmp_path)
    data = json.loads((tmp_path / SESSION_RELPATH).read_text())
    assert data["branch"] == "feature/x"


def test_live_state_preserved_without_force(tmp_path: Path):
    scaffold_session(repo=tmp_path)
    session = tmp_path / SESSION_RELPATH
    session.write_text(json.dumps({"schema": 1, "task": "in progress"}) + "\n")

    scaffold_session(repo=tmp_path)  # second run, no force
    assert json.loads(session.read_text())["task"] == "in progress"


def test_force_overwrites_live_state(tmp_path: Path):
    scaffold_session(repo=tmp_path)
    session = tmp_path / SESSION_RELPATH
    session.write_text(json.dumps({"schema": 1, "task": "stale"}) + "\n")

    scaffold_session(repo=tmp_path, force=True)
    assert json.loads(session.read_text())["task"] is None


def test_protocol_always_rewritten(tmp_path: Path):
    scaffold_session(repo=tmp_path)
    protocol = tmp_path / PROTOCOL_RELPATH
    protocol.write_text("clobbered")
    scaffold_session(repo=tmp_path)  # no force
    assert "Shared agent session state" in protocol.read_text()


def test_session_file_is_gitignored_but_not_protocol(tmp_path: Path):
    update_gitignore(repo=tmp_path)
    content = (tmp_path / ".gitignore").read_text()
    assert SESSION_RELPATH in content
    assert PROTOCOL_RELPATH not in GITIGNORE_ENTRIES


def test_toolkit_session_public_surface(tmp_path: Path):
    path = toolkit.session(tmp_path)
    assert path == (tmp_path / SESSION_RELPATH).resolve()
    assert path.exists()
