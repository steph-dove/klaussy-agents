"""No scaffolded skill reaches an agent with an unresolved `{{TOKEN}}` in it.

`tests/evals/test_no_token_leaks.py` guards the two eval harnesses. It cannot
guard this: the harnesses render skill bodies their own way, so a token map that
only the scaffolder uses is invisible to them. That is how `{{BASE_RESOLUTION}}`
shipped literally to nine of the ten agents for three releases, while both eval
suites were green.

This walks the real writers instead, every backend in `BACKENDS`, and reads what
lands on disk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from klaussy.agents.backends import BACKENDS

_TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")

# Where each backend writes skills. A backend missing from here is a new agent
# whose output nothing checks, so the test says so rather than skipping it.
_SKILL_DIRS = (
    ".claude/skills",
    ".gemini/skills",
    ".cursor/skills",
    ".github/skills",
    ".agents/skills",
    ".opencode/skills",
    ".kimi-code/skills",
    ".codex/skills",
    ".cline/skills",
    ".aider/skills",
    ".gemini/antigravity-cli",
)


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory) -> Path:
    """One repo with every backend's skills written into it."""
    repo = tmp_path_factory.mktemp("scaffold")
    (repo / "pyproject.toml").write_text('name = "demo"\n')
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)

    for backend in BACKENDS.values():
        backend.run_skills(repo, force=True, base_branch="main", review_template=None)
    return repo


def test_every_backend_resolves_every_token(scaffolded: Path):
    leaks: dict[str, set[str]] = {}
    for path in scaffolded.rglob("*.md"):
        found = set(_TOKEN.findall(path.read_text()))
        if found:
            leaks[str(path.relative_to(scaffolded))] = found

    assert not leaks, "unresolved tokens in scaffolded skills:\n" + "\n".join(
        f"  {name}: {sorted(tokens)}" for name, tokens in sorted(leaks.items())
    )


def test_the_base_resolution_block_actually_lands(scaffolded: Path):
    """The leak's specific shape: present as a token, absent as prose.

    A token map missing `BASE_RESOLUTION` substitutes nothing and leaves the
    literal behind, so this pins the text as well as the absence of the token.
    """
    written = [p for p in scaffolded.rglob("*.md") if "Resolve the base first" in p.read_text()]
    dirs = {
        next((d for d in _SKILL_DIRS if str(p.relative_to(scaffolded)).startswith(d)), "?")
        for p in written
    }
    assert "?" not in dirs, f"skills written somewhere _SKILL_DIRS doesn't cover: {dirs}"
    assert len(dirs) >= 7, f"only {sorted(dirs)} carry the base-resolution block"
