"""Eval: the explain skill explains the snippet in plain, tell-free prose.

Asserts the explanation names what the function does (its clamping behavior) and
reads human, since explain output carries the humanize spec.

Tell-freeness is checked at the layer that owns each tell. The *phrase* tells
(chatbot scaffolding, filler openers) are what the {{HUMANIZE}} prompt reliably
controls, so they're asserted on the raw draft. The em-dash is the one tell a
prompt can't deterministically eliminate — that's the job of klaussy's
deterministic scrubber (the whole reason it exists) — so we instead assert the
scrubber delivers tell-free prose. This tests both layers and stays stable
instead of flaking on a probabilistic em-dash the model slips into a draft.
"""

from __future__ import annotations

import harness

from klaussy.humanize import humanize

CONTEXT = """\
Explain this function:

    def clamp(value, low, high):
        if value < low:
            return low
        if value > high:
            return high
        return value
"""


@harness.requires_eval_env
def test_explanation_names_behavior_and_reads_human():
    out = harness.run_skill(
        "explain",
        CONTEXT,
        instruction="Explain what this code does.",
        max_tokens=1200,
    )
    low = out.lower()

    assert "clamp" in low, f"doesn't name the function: {out!r}"
    assert any(k in low for k in ("bound", "range", "limit", "between", "minimum", "maximum")), (
        f"doesn't describe the clamping behavior: {out!r}"
    )

    # Phrase tells (scaffolding, filler) are prompt-controllable — the raw draft
    # must be free of them.
    phrase_tells = [t for t in harness.ai_tells_present(out) if t != "—"]
    assert not phrase_tells, f"chatbot phrase tells in explanation: {phrase_tells}: {out!r}"

    # The em-dash is the deterministic scrubber's domain; verify klaussy's
    # humanizer delivers tell-free prose (catches a scrubber regression or a tell
    # it can't clean, without flaking on a draft em-dash it removes fine).
    assert not harness.ai_tells_present(humanize(out)), (
        f"tells survive klaussy's deterministic scrubber: {out!r}"
    )
