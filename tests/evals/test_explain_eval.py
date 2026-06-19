"""Eval: the explain skill explains the snippet in plain, tell-free prose.

Asserts the explanation names what the function does (its clamping behavior) and
reads human (no AI tells), since explain output also carries the humanize spec.
"""

from __future__ import annotations

import harness

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

    tells = harness.ai_tells_present(out)
    assert not tells, f"AI tells in explanation: {tells}: {out!r}"
