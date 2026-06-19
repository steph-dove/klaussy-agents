"""End-to-end eval: the fix skill makes ruff pass without breaking the suite.

The ground truth here is objective and needs no judge: after the agent runs,
`ruff check` must exit 0 and the pre-existing test suite must still pass (so the
fix changed style, not behavior). This is the PoC that establishes the
runner + fixture + side-effect pattern for the other objective skills
(test/debug/refactor).
"""

from __future__ import annotations

import e2e_harness as e2e

# A file with two ruff findings: F401 (unused import) and E711 (== None).
UTIL_BAD = "import os\n\n\ndef is_empty(x):\n    return x == None\n"

# A suite that pins behavior: passing before AND after the fix proves the fix
# was style-only. is_empty(None) is True; anything else is False.
TEST_OK = (
    "from util import is_empty\n\n\n"
    "def test_is_empty_none():\n"
    "    assert is_empty(None) is True\n\n\n"
    "def test_is_empty_value():\n"
    "    assert is_empty('x') is False\n"
)

PYPROJECT = "[tool.ruff]\nline-length = 100\n"


@e2e.requires_e2e
def test_fix_skill_makes_ruff_clean_and_keeps_tests_green(tmp_path):
    repo = tmp_path
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "util.py").write_text(UTIL_BAD)
    (repo / "test_util.py").write_text(TEST_OK)
    e2e.git(repo, "init", "-q")
    e2e.git(repo, "add", "-A")
    e2e.git(repo, "-c", "user.email=e@e", "-c", "user.name=e", "commit", "-qm", "init")

    # --- Baseline: ruff fails, tests pass. ---
    assert e2e.sh(repo, "ruff", "check", ".").returncode != 0, "fixture should have lint errors"
    assert e2e.pytest_run(repo).returncode == 0, "fixture suite should start green"

    # --- Run the agent. ---
    proc = e2e.run_skill_agent(repo, "fix", "Fix all lint errors in this repo.")
    assert proc.returncode == 0, f"agent failed: {proc.stderr[-2000:]}"

    # --- Side effects: ruff clean, suite STILL green (behavior preserved). ---
    ruff_after = e2e.sh(repo, "ruff", "check", ".")
    assert ruff_after.returncode == 0, f"ruff still failing:\n{ruff_after.stdout}"
    assert e2e.pytest_run(repo).returncode == 0, "fix changed behavior: suite went red"

    # --- The fix actually landed in the source. ---
    util = (repo / "util.py").read_text()
    assert "is None" in util, f"E711 not fixed:\n{util}"
    assert "import os" not in util, f"unused import not removed:\n{util}"
    assert "def is_empty" in util, f"function was dropped/rewritten:\n{util}"
