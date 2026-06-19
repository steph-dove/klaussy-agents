"""End-to-end eval: the debug skill fixes a real bug and proves it with a test.

Ground truth is independent of the agent's own tests: a buggy `parse_range`
returns an exclusive range; after the debug skill runs, the corrected behavior
is checked directly (`parse_range('1-3') == [1, 2, 3]`), the suite is green, and
the agent left behind a regression test (the skill's "write a failing test"
discipline). The behavior check is the objective signal; it can't be gamed.
"""

from __future__ import annotations

import e2e_harness as e2e

# Bug: parse_range is exclusive (range(lo, hi)); it should be inclusive.
# parse_range('1-3') returns [1, 2] but should return [1, 2, 3]. It's uncovered
# by the existing suite, which is why the bug "shipped".
CALC_BUGGY = (
    "def add(a, b):\n"
    "    return a + b\n\n\n"
    "def parse_range(s):\n"
    '    lo, hi = s.split("-")\n'
    "    return list(range(int(lo), int(hi)))\n"
)

TEST_BASE = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"

PYPROJECT = "[tool.ruff]\nline-length = 100\n"

BUG_REPORT = (
    "parse_range(s) in calc.py should expand an inclusive range: parse_range('1-3') "
    "must return [1, 2, 3] and parse_range('5-5') must return [5]. Right now it drops "
    "the last number (returns [1, 2] and [] respectively). Diagnose and fix it."
)

BEHAVIOR_CHECK = (
    "from calc import parse_range\n"
    "assert parse_range('1-3') == [1, 2, 3], parse_range('1-3')\n"
    "assert parse_range('5-5') == [5], parse_range('5-5')\n"
)


def _test_files(repo):
    return list(repo.glob("test_*.py")) + list(repo.glob("**/test_*.py"))


@e2e.requires_e2e
def test_debug_skill_fixes_bug_and_adds_regression_test(tmp_path):
    repo = tmp_path
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "calc.py").write_text(CALC_BUGGY)
    (repo / "test_calc.py").write_text(TEST_BASE)
    e2e.git(repo, "init", "-q")
    e2e.git(repo, "add", "-A")
    e2e.git(repo, "-c", "user.email=e@e", "-c", "user.name=e", "commit", "-qm", "init")

    # Baseline: suite is green (bug is uncovered) but the behavior is wrong.
    assert e2e.pytest_run(repo).returncode == 0, "fixture suite should start green"
    assert e2e.python_c(repo, BEHAVIOR_CHECK).returncode != 0, "bug should be present"

    proc = e2e.run_skill_agent(repo, "debug", BUG_REPORT)
    assert proc.returncode == 0, f"agent failed: {proc.stderr[-2000:]}"

    # Objective ground truth: behavior is now correct, and the suite is green.
    fixed = e2e.python_c(repo, BEHAVIOR_CHECK)
    assert fixed.returncode == 0, f"bug not fixed:\n{fixed.stderr[-1500:]}"
    assert e2e.pytest_run(repo).returncode == 0, "suite not green after fix"

    # Discipline: a regression test for parse_range was added.
    covers = any("parse_range" in f.read_text() for f in _test_files(repo))
    assert covers, "no regression test references parse_range"
