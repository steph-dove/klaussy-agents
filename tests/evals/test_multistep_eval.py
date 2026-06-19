"""Smoke evals for the multi-step skills (debug / refactor / plan / implement).

These skills are agentic: they investigate, plan, and edit across many turns and
tools. A single-shot prompt eval can't exercise that loop, so these are
deliberately shallow: they only check that each skill's *defining discipline*
surfaces in its opening response (debug reproduces before fixing, refactor
guards behavior with a test baseline, plan/implement investigate before editing).
A pass here means "the spec points the model the right way," not "the skill
works end to end." Keep the keyword sets loose to avoid flakiness.
"""

from __future__ import annotations

import harness
import pytest

# (label, skill, context, instruction, any-of keywords that signal the discipline)
CASES = [
    (
        "debug-reproduces-first",
        "debug",
        "Bug: get_user('abc') returns a 500 in production but works locally.\n"
        "    def get_user(uid):\n"
        "        return db.execute('SELECT * FROM users WHERE id = ' + uid)",
        "Help me debug this.",
        ["reproduce", "root cause", "root-cause", "failing test"],
    ),
    (
        "refactor-guards-behavior",
        "refactor",
        "Refactor src/util.py to extract the input validation into a helper.\n"
        "    def save(x):\n"
        "        if not x or len(x) > 100: raise ValueError\n"
        "        return store(x)",
        "Refactor this.",
        ["behavior", "baseline", "tests pass", "preserve", "same behavior"],
    ),
    (
        "plan-investigates-first",
        "plan",
        "Add per-user rate limiting to the public API.",
        "Plan and implement this.",
        ["phase", "step", "investigat", "discovery", "clarif", "explore"],
    ),
    (
        "implement-scopes-first",
        "implement",
        "Ticket FEAT-12: add a --json flag to the `export` command that emits the "
        "report as JSON instead of the table.",
        "Implement this ticket.",
        ["scope", "plan", "investigat", "understand", "clarif", "failing test"],
    ),
]


@harness.requires_eval_env
@pytest.mark.parametrize(
    "label,skill,context,instruction,any_of", CASES, ids=[c[0] for c in CASES]
)
def test_multistep_discipline_surfaces(label, skill, context, instruction, any_of):
    out = harness.run_skill(skill, context, instruction=instruction, max_tokens=1200)
    low = out.lower()
    assert any(k in low for k in any_of), (
        f"[{label}] {skill} skill didn't surface its discipline ({any_of}): {out!r}"
    )
