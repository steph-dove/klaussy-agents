"""plan's check phase, driven for real.

Two things a prompt eval can't see. The adversarial reviewer is a sub-agent, so
whether one is spawned at all, and what the orchestrator hands it, only exist in
a real loop. And "this skill plans, it does not build" is a claim about what is
*not* on disk afterwards.

Costs one real agent run, and one that fans out; see e2e_harness.py for the gate.
"""

from __future__ import annotations

from pathlib import Path

import e2e_harness as harness

SKILL = "plan"

CLIENT = '''"""HTTP client."""

import requests


def fetch(url):
    """Fetch a URL and return the decoded body."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()
'''

PROMPT = (
    "Use the shop-plan skill to plan this task: add retry with backoff to fetch() in "
    "src/client.py. Answering your clarifying questions up front so you don't have to "
    "ask: three attempts, exponential backoff, retry only on 5xx and timeouts, no config "
    "knob, no new dependencies. I confirm the scope and approve the plan in advance. Go "
    "all the way through writing plan.md and checking it, then stop without implementing."
)


def _build(tmp_path: Path, attempt: int) -> Path:
    root = tmp_path / f"attempt{attempt}"
    root.mkdir()
    work = root / "shop"
    (work / "src").mkdir(parents=True)
    (work / "src" / "client.py").write_text(CLIENT)
    (work / "CLAUDE.md").write_text(
        "# shop\n\n## Commands\n\n```bash\npytest\n```\n\n## Conventions\n\n"
        "- **Style**: snake_case, no new dependencies without a decision record.\n"
    )
    harness.git(work.parent, "init", "-q", "-b", "main", str(work))
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        harness.git(work, "config", key, value)
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "chore: base")
    harness.install_skills(work)
    return work


def _check_one_run(repo: Path) -> None:
    calls, final = harness.run_agent(repo, PROMPT, timeout=900)
    trace = "tool calls:\n" + "\n".join(c[:300] for c in calls) + f"\nagent said:\n{final[:1200]}"

    plan = repo / "plan.md"
    assert plan.exists(), f"no plan.md was written. {trace}"
    body = plan.read_text()
    assert "## Build sequence" in body, f"plan.md has no build sequence:\n{body[:1200]}"
    assert "## Plan review" in body, f"the check phase left no record:\n{body[:1200]}"

    # The adversarial reviewer is a sub-agent, and it gets the path, not the plan.
    reviewers = [c for c in calls if c.startswith(("Task:", "Agent:")) and "plan.md" in c]
    assert reviewers, f"no sub-agent was sent to attack the plan. {trace}"
    assert not any("## Build sequence" in r for r in reviewers), (
        f"the plan's body was pasted into the reviewer instead of its path. {trace}"
    )

    # Planning is not building.
    assert (repo / "src" / "client.py").read_text() == CLIENT, "plan edited the source"
    assert not harness.git(repo, "status", "--porcelain", "src").stdout.strip(), (
        f"plan left changes under src/. {trace}"
    )


@harness.requires_e2e
def test_the_plan_is_checked_and_nothing_is_built(tmp_path: Path):
    """One retry on a fresh repo: an agent loop varies, a broken phase doesn't."""
    try:
        _check_one_run(_build(tmp_path, 1))
    except AssertionError as first:
        try:
            _check_one_run(_build(tmp_path, 2))
        except AssertionError as second:
            raise AssertionError(f"both attempts fell short.\n\nfirst:\n{first}") from second
