"""End-to-end eval: the test skill writes tests that actually catch a regression.

Ground truth is a mutation check: after the agent writes tests for a new
function and the suite is green, we replace the function with a broken
implementation and re-run. If the generated tests are real, the suite must go
red. A test that passes against the mutant is worthless, and this fails it.
"""

from __future__ import annotations

import e2e_harness as e2e

CALC_BASE = "def add(a, b):\n    return a + b\n"

# Added as an uncommitted change so the test skill (which reads `git diff`) sees
# it as the current work to cover.
CLAMP_SRC = (
    "\n\ndef clamp(value, low, high):\n"
    "    if value < low:\n"
    "        return low\n"
    "    if value > high:\n"
    "        return high\n"
    "    return value\n"
)

TEST_BASE = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"

# The mutant: clamp ignores its bounds. Boundary tests must catch this.
CALC_MUTANT = (
    "def add(a, b):\n    return a + b\n\n\ndef clamp(value, low, high):\n    return value\n"
)

PYPROJECT = "[tool.ruff]\nline-length = 100\n"


def _test_files(repo):
    return list(repo.glob("test_*.py")) + list(repo.glob("**/test_*.py"))


@e2e.requires_e2e
def test_test_skill_writes_tests_that_catch_a_mutation(tmp_path):
    repo = tmp_path
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "calc.py").write_text(CALC_BASE)
    (repo / "test_calc.py").write_text(TEST_BASE)
    e2e.git(repo, "init", "-q")
    e2e.git(repo, "add", "-A")
    e2e.git(repo, "-c", "user.email=e@e", "-c", "user.name=e", "commit", "-qm", "init")

    # The change to cover: a new clamp function, left uncommitted.
    (repo / "calc.py").write_text(CALC_BASE + CLAMP_SRC)
    assert e2e.pytest_run(repo).returncode == 0, "fixture suite should start green"

    proc = e2e.run_skill_agent(
        repo, "test", "Write tests for the current changes (the new clamp function)."
    )
    assert proc.returncode == 0, f"agent failed: {proc.stderr[-2000:]}"

    # The agent's tests pass, and they actually test clamp.
    assert e2e.pytest_run(repo).returncode == 0, "agent's own tests don't pass"
    covers_clamp = any("clamp(" in f.read_text() for f in _test_files(repo))
    assert covers_clamp, "no test references clamp()"

    # Mutation: break clamp's bounds. Real boundary tests must now fail.
    (repo / "calc.py").write_text(CALC_MUTANT)
    mutant = e2e.pytest_run(repo)
    assert mutant.returncode != 0, (
        "tests passed against a broken clamp, so they don't test its behavior:\n"
        f"{mutant.stdout[-1500:]}"
    )
