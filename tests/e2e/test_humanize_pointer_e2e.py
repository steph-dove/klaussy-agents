"""The prose skills point at the humanize skill instead of carrying its rules.

That only works if an agent actually follows the pointer, which the prompt evals
in tests/evals/ can't show: they disable every tool and run in an empty
directory, so the skill named in the pointer isn't reachable. This installs the
skills into a throwaway repo and drives a real agent loop over them.

See e2e_harness.py for the gate; this costs a real agent run.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import e2e_harness as harness
import pytest

from klaussy import toolkit

_SUBJECT = re.compile(r"^(feat|fix|refactor|test|docs|chore|style|perf)(\([^)]+\))?: .+")
PROMPT = "Write the commit message for the staged changes, using this repo's probe-commit skill."


def _git(repo: Path, *args: str) -> None:
    """`harness.git` never raises, and a silent setup failure blames the skill."""
    proc = harness.git(repo, *args)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "probe"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main", ".")
    _git(work, "config", "user.name", "Dev")
    _git(work, "config", "user.email", "dev@example.com")
    (work / "CLAUDE.md").write_text("# probe\n\n## Commands\n\n```bash\npytest\n```\n")
    (work / "api.py").write_text("def fetch(url):\n    return get(url)\n")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "chore: base")
    (work / "api.py").write_text(
        "def fetch(url):\n"
        "    for attempt in range(3):\n"
        "        try:\n"
        "            return get(url, timeout=5)\n"
        "        except Timeout:\n"
        "            continue\n"
        "    raise\n"
    )
    _git(work, "add", ".")
    # Through the toolkit, not the `klaussy` on PATH, which may be an older install.
    result = toolkit.skills(work, agents="claude", base_branch="main")
    assert not result.skipped, f"skill scaffold skipped: {result.skipped}"
    return work


def _run(repo: Path) -> tuple[list[str], str]:
    """Return (tool invocations, final message) from one headless agent run."""
    proc = subprocess.run(
        [
            "claude",
            "-p",
            PROMPT,
            "--permission-mode",
            "bypassPermissions",
            "--model",
            os.environ.get("KLAUSSY_E2E_MODEL", harness.DEFAULT_MODEL),
            "--output-format",
            "stream-json",
            "--verbose",
            "--add-dir",
            str(repo),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, f"the agent run itself failed: {proc.stderr[-800:]}"
    used: list[str] = []
    final = ""
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for block in (event.get("message") or {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                arg = block.get("input", {})
                detail = arg.get("skill") or arg.get("file_path") or arg.get("command") or ""
                used.append(f"{block.get('name', '')}: {detail}")
        if event.get("type") == "result":
            final = event.get("result", "")
    return used, final


@harness.requires_e2e
def test_the_commit_skill_reaches_for_humanize(repo: Path):
    used, final = _run(repo)
    assert any("probe-commit" in u for u in used), f"never used the commit skill: {used}"
    assert any("humanize" in u.lower() for u in used), (
        f"the pointer was not followed, so the rules never reached the message: {used}"
    )
    assert final, "no final message"
    # The agent narrates its passes around the message; judge the message itself,
    # which starts at the conventional subject line.
    lines = final.splitlines()
    start = next((i for i, x in enumerate(lines) if _SUBJECT.match(x.strip())), None)
    assert start is not None, f"no conventional subject in: {final!r}"
    message = "\n".join(lines[start:])
    assert "—" not in message, f"em-dash survived the humanize pass: {message!r}"
