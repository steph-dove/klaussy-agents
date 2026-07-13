"""Tests for the cross-agent dependency gate (new-dependency speed bump)."""

import importlib.util
import io
import json
from pathlib import Path

import pytest

from klaussy import hooks as hooks_mod

TEMPLATES = Path(hooks_mod.__file__).parent / "templates" / "hooks"


def _load(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, TEMPLATES / relpath)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def guard():
    return _load("multi/dependency_guard.py", "_dependency_guard")


# Commands that ADD a new named dependency → the package list the guard reports.
@pytest.mark.parametrize(
    "command,expected",
    [
        ("npm install lodash", ["lodash"]),
        ("npm i lodash react", ["lodash", "react"]),
        ("npm add lodash", ["lodash"]),
        ("pnpm add zod", ["zod"]),
        ("yarn add react", ["react"]),
        ("bun add hono", ["hono"]),
        ("pip install requests", ["requests"]),
        ("pip3 install flask", ["flask"]),
        ("python -m pip install flask", ["flask"]),
        ("uv add pydantic", ["pydantic"]),
        ("uv pip install rich", ["rich"]),
        ("poetry add httpx", ["httpx"]),
        ("cargo add serde", ["serde"]),
        ("gem install rails", ["rails"]),
        ("go get github.com/foo/bar", ["github.com/foo/bar"]),
        ("pip install --upgrade requests", ["requests"]),
    ],
)
def test_detects_new_dependency(guard, command, expected):
    assert guard._added_packages(command) == expected


# Commands that only sync an existing manifest → nothing added.
@pytest.mark.parametrize(
    "command",
    [
        "npm install",
        "npm ci",
        "pnpm install",
        "yarn",
        "yarn install",
        "pip install -r requirements.txt",
        "pip install -e .",
        "pip install .",
        "poetry install",
        "uv sync",
        "echo hello",
        "git commit -m wip",
    ],
)
def test_ignores_manifest_sync(guard, command):
    assert guard._added_packages(command) == []


def test_bypass_token_allows(guard):
    assert guard._added_packages("KLAUSSY_DEPS_OK=1 pip install requests") == []


def _run(guard, payload, monkeypatch) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    return guard.main(), err.getvalue()


def test_main_blocks_new_dependency(guard, monkeypatch):
    rc, err = _run(guard, {"tool_input": {"command": "pip install requests"}}, monkeypatch)
    assert rc == 2
    assert "requests" in err
    assert "KLAUSSY_DEPS_OK=1" in err


def test_main_allows_manifest_sync(guard, monkeypatch):
    rc, err = _run(guard, {"tool_input": {"command": "npm install"}}, monkeypatch)
    assert rc == 0
    assert err == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"toolArgs": {"command": "pip install requests"}},  # Copilot CLI shape
        {"command": "pip install requests"},  # Cursor top-level shape
    ],
)
def test_main_reads_each_agent_payload_shape(guard, payload, monkeypatch):
    rc, _ = _run(guard, payload, monkeypatch)
    assert rc == 2


def test_main_never_crashes_on_garbage(guard, monkeypatch):
    rc, _ = _run(guard, ["not", "a", "dict"], monkeypatch)
    assert rc == 0


class _FakeStdin:
    """Stand-in for a real stdin: exposes a bytes `.buffer` like sys.stdin does.

    The StringIO the other tests use has no `.buffer`, so it exercises the str
    fallback path. This exercises the byte path the guards actually hit at
    runtime — where an em-dash arrives as UTF-8 bytes, not decoded text.
    """

    def __init__(self, raw: bytes):
        self.buffer = io.BytesIO(raw)


def test_main_decodes_utf8_stdin(guard, monkeypatch):
    # Non-ASCII bytes (em-dash + CJK) would raise UnicodeDecodeError under a
    # Windows cp1252 locale with the old json.load(sys.stdin); the guard must
    # decode UTF-8 from stdin.buffer and still block the new dependency.
    payload = {"tool_input": {"command": "pip install requests"}, "note": "em—dash 包子"}
    monkeypatch.setattr("sys.stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    assert guard.main() == 2
    assert "requests" in err.getvalue()
