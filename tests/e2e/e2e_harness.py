"""Harness for opt-in END-TO-END skill evals.

Unlike the prompt evals (tests/evals/), these run a *real agent loop with tools*
against a throwaway git repo and assert on side effects, the linter's exit code,
the test suite still being green, the actual file edits, not on a returned
string. They drive the `claude` CLI in headless mode (`-p`), so they reuse its
existing auth (no ANTHROPIC_API_KEY needed) and cost real tokens and minutes per
case.

Gated hard: skipped unless `KLAUSSY_RUN_E2E=1` and both `claude` and `ruff` are
installed. Run locally with:

    KLAUSSY_RUN_E2E=1 uv run --with pytest --with ruff python -m pytest tests/e2e -v -s

Scope note: the PoC drives the skill by handing the agent the skill's spec
directly. A fuller version would `klaussy skills` the fixture repo and let the
skill auto-trigger; this is the thinner, deterministic slice that proves the
runner + fixture + side-effect-assertion pattern.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from klaussy.agents.render import permission_target_markdown
from klaussy.skills import (
    _CLAUDE_PERMISSION_SYNTAX,
    _CLAUDE_PERMISSIONS_FILE,
    SKILL_TEMPLATE_ROOT,
    render_tokens,
    skill_tokens,
)

DEFAULT_MODEL = "claude-sonnet-4-6"

requires_e2e = pytest.mark.skipif(
    os.environ.get("KLAUSSY_RUN_E2E") != "1"
    or shutil.which("claude") is None
    or shutil.which("ruff") is None,
    reason="opt-in e2e: set KLAUSSY_RUN_E2E=1 and install the claude + ruff CLIs",
)

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_DYNAMIC_SHELL = re.compile(r"```!\n.*?\n```", re.DOTALL)


def load_skill_body(skill: str, *, repo: str = "myrepo", base_branch: str = "main") -> str:
    """Return the substituted SKILL.md body, frontmatter + ```! blocks stripped."""
    text = (
        resources.files("klaussy")
        .joinpath(f"{SKILL_TEMPLATE_ROOT}/{skill}/SKILL.md.tmpl")
        .read_text()
    )
    text = render_tokens(
        text,
        skill_tokens(
            repo_namespace=repo,
            base_branch=base_branch,
            permissions_target=permission_target_markdown(
                "Claude Code", _CLAUDE_PERMISSIONS_FILE, _CLAUDE_PERMISSION_SYNTAX
            ),
        ),
    )
    text = _FRONTMATTER.sub("", text, count=1)
    text = _DYNAMIC_SHELL.sub("", text)
    return text.strip()


def sh(repo: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command in `repo`, capturing output. Never raises on non-zero."""
    return subprocess.run(list(args), cwd=repo, capture_output=True, text=True, timeout=timeout)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return sh(repo, "git", *args)


def pytest_run(repo: Path) -> subprocess.CompletedProcess:
    """Run the fixture repo's own test suite with the current interpreter."""
    return sh(repo, sys.executable, "-m", "pytest", "-q")


def python_c(repo: Path, code: str) -> subprocess.CompletedProcess:
    """Run `python -c code` in the fixture repo. Exit 0 means the asserts held."""
    return sh(repo, sys.executable, "-c", code)


def install_skills(repo: Path, agent: str = "claude", base_branch: str = "main") -> None:
    """Scaffold the real skills into `repo` so the agent can reach them by name."""
    from klaussy import toolkit

    result = toolkit.skills(repo, agents=agent, base_branch=base_branch)
    assert not result.skipped, f"skill scaffold skipped: {result.skipped}"


def run_agent(
    repo: Path,
    prompt: str,
    *,
    path_prefix: Path | None = None,
    model: str | None = None,
    timeout: int = 600,
) -> tuple[list[str], str]:
    """Drive a real agent loop over `repo`; return its tool calls and final message.

    Unlike `run_skill_agent`, the skills are installed in the repo rather than
    pasted into the prompt, so what the agent reads and invokes is its own
    choice — which is the thing worth asserting on. `path_prefix` goes in front
    of PATH, for a recording stand-in like a fake `gh`.
    """
    env = dict(os.environ)
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    proc = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "bypassPermissions",
            "--model",
            model or os.environ.get("KLAUSSY_E2E_MODEL", DEFAULT_MODEL),
            "--output-format",
            "stream-json",
            "--verbose",
            "--add-dir",
            str(repo),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    assert proc.returncode == 0, f"the agent run itself failed: {proc.stderr[-800:]}"
    calls: list[str] = []
    final = ""
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for block in (event.get("message") or {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                arg = block.get("input", {})
                # A sub-agent's prompt is what the orchestrator chose to hand it,
                # which is the thing worth asserting on for a fan-out skill.
                detail = (
                    arg.get("skill")
                    or arg.get("command")
                    or arg.get("file_path")
                    or arg.get("prompt")
                    or arg.get("description")
                    or ""
                )
                calls.append(f"{block.get('name', '')}: {detail}")
        if event.get("type") == "result":
            final = event.get("result", "")
    return calls, final


def run_skill_agent(
    repo: Path, skill: str, task: str, *, model: str | None = None, timeout: int = 360
) -> subprocess.CompletedProcess:
    """Drive `skill` over `repo` via headless `claude`, returning the finished process.

    Tools run with permissions bypassed because the target is a throwaway fixture
    repo under tmp. Output is the agent's final printed message; the real signal
    is what it changed on disk (asserted by the caller).
    """
    prompt = (
        f"Follow this skill exactly:\n\n{load_skill_body(skill)}\n\n"
        f"---\nTask: {task}\nWork only inside this repository. Stop when done."
    )
    return subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "bypassPermissions",
            "--model",
            model or os.environ.get("KLAUSSY_E2E_MODEL", DEFAULT_MODEL),
            "--add-dir",
            str(repo),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
