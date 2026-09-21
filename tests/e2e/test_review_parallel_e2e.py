"""review's parallel path, driven for real.

Splitting the review into `parallel.md` and one file per lens only pays off if
the orchestrator actually opens them at the 150-line threshold. A prompt eval
can't tell: it has no filesystem, so the pointer resolves to nothing and the
model reviews from the diff in front of it either way.

This builds a branch over the threshold with a planted bug, then checks that the
parallel path was loaded, that the lenses reached the sub-agents, and that the
review found the bug.

Costs one real agent run, and a fan-out one; see e2e_harness.py for the gate.
"""

from __future__ import annotations

from pathlib import Path

import e2e_harness as harness

SKILL = "review"

PROMPT = "Use the shop-review skill to review this branch against main."


# Enough real code to clear the 150-line triage threshold.
def _module(n: int) -> str:
    return "\n".join(
        [
            f'"""Report helpers, group {n}."""',
            "",
            "",
            f"def summarize_{n}(rows):",
            '    """Total the amounts on a batch of rows."""',
            "    total = 0",
            "    for row in rows:",
            '        total += row["amount"]',
            "    return total",
            "",
            "",
            f"def average_{n}(rows):",
            '    """Mean amount across the batch."""',
            f"    return summarize_{n}(rows) / len(rows)",
            "",
            "",
            f"def labels_{n}(rows):",
            '    """Human labels for a batch."""',
            '    return [row.get("label", "unlabelled") for row in rows]',
            "",
        ]
    )


# The planted bug: the cache is read before the lock is taken, so two callers
# can both miss and both write. A correctness lens should catch it.
RACY = '''"""Session cache."""

import threading

_lock = threading.Lock()
_cache = {}


def get_session(key, load):
    """Return the cached session, loading it once."""
    if key in _cache:
        return _cache[key]
    session = load(key)
    with _lock:
        _cache[key] = session
    return session
'''


def _build(tmp_path: Path, attempt: int) -> Path:
    root = tmp_path / f"attempt{attempt}"
    root.mkdir()
    work = root / "shop"
    work.mkdir()
    harness.git(work.parent, "init", "-q", "-b", "main", str(work))
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        harness.git(work, "config", key, value)
    (work / "CLAUDE.md").write_text("# shop\n\n## Commands\n\n```bash\npytest\n```\n")
    (work / "README.md").write_text("# shop\n")
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "chore: base")
    harness.git(work, "checkout", "-q", "-b", "feat/reports")
    src = work / "src"
    src.mkdir()
    for n in range(1, 9):
        (src / f"reports_{n}.py").write_text(_module(n))
    (src / "session_cache.py").write_text(RACY)
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "feat: reporting helpers and a session cache")
    harness.install_skills(work)
    return work


def _check_one_run(repo: Path) -> None:
    calls, final = harness.run_agent(repo, PROMPT, timeout=900)
    trace = "tool calls:\n" + "\n".join(c[:200] for c in calls) + f"\nagent said:\n{final[:1500]}"

    joined = "\n".join(calls)
    assert "parallel.md" in joined, f"the parallel path was never opened. {trace}"
    assert "lens-" in joined, f"no lens file reached a reviewer. {trace}"

    output = repo / "REVIEW_OUTPUT.md"
    assert output.exists(), f"no REVIEW_OUTPUT.md was written. {trace}"
    review = output.read_text().lower()
    assert "session_cache" in review, f"the planted race was never reviewed:\n{review[:1500]}"
    assert any(word in review for word in ("race", "lock", "concurrent", "both")), (
        f"the race was not described as one:\n{review[:1500]}"
    )


@harness.requires_e2e
def test_large_diffs_load_the_parallel_path_and_its_lenses(tmp_path: Path):
    """One retry on a fresh repo: an agent loop varies, a broken pointer doesn't."""
    try:
        _check_one_run(_build(tmp_path, 1))
    except AssertionError as first:
        try:
            _check_one_run(_build(tmp_path, 2))
        except AssertionError as second:
            raise AssertionError(f"both attempts fell short.\n\nfirst:\n{first}") from second
