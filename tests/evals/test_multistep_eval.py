"""Smoke evals for the multi-step skills (debug / refactor / qa).

These skills are agentic: they investigate, plan, and edit across many turns and
tools. A single-shot prompt eval can't exercise that loop, so these are
deliberately shallow: they only check that each skill's *defining discipline*
surfaces in its opening response (debug reproduces before fixing, refactor
guards behavior with a test baseline, qa captures the evidence that fits the
change). A pass here means "the spec points the model the right way," not "the
skill works end to end."

`plan`, `implement`, and `rest-of-the-owl` are intentionally NOT here: their
specs drive a full multi-phase loop (enter plan mode, investigate, run the whole
dev cycle), which a single completion can't bound — the model generates the whole
plan, or (for the owl) deflects to a workflow opt-in, so the defining discipline
doesn't reliably surface in one turn. Evaluating them needs the e2e harness (real
tools, approval handling), not a prompt eval. `debug` also has a real e2e
(tests/e2e/test_debug_e2e.py); it stays here as a cheap fast check too. Keep the
keyword sets loose.
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
        # QA's discipline: pick the evidence that fits the change — a UI change
        # gets screenshots (not just tests). Loose keywords for the UI signal.
        "qa-screenshots-ui-change",
        "qa",
        "Changed src/components/LoginForm.jsx — restyled the submit button and "
        "added an inline error banner when auth fails.",
        "QA this change and tell me what evidence you'll capture.",
        ["screenshot", "downloads"],
    ),
]


@harness.requires_eval_env
@pytest.mark.parametrize("label,skill,context,instruction,any_of", CASES, ids=[c[0] for c in CASES])
def test_multistep_discipline_surfaces(label, skill, context, instruction, any_of):
    out = harness.run_skill(skill, context, instruction=instruction, max_tokens=1200)
    low = out.lower()
    assert any(k in low for k in any_of), (
        f"[{label}] {skill} skill didn't surface its discipline ({any_of}): {out!r}"
    )
