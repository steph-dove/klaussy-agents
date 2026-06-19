"""Eval: the test skill writes a runnable test that covers the boundaries.

Feeds a small pure function and asserts the generated test calls it, has real
assertions, and reaches at least one boundary (not just the happy path).
"""

from __future__ import annotations

import harness

CONTEXT = """\
New function in src/util.py to write tests for (pytest is the framework):

    def clamp(value, low, high):
        if value < low:
            return low
        if value > high:
            return high
        return value
"""


@harness.requires_eval_env
def test_generated_test_calls_function_and_covers_boundaries():
    out = harness.run_skill(
        "test",
        CONTEXT,
        instruction="Write the pytest tests for this function. Output only the test code.",
        max_tokens=1500,
    )
    low = out.lower()

    assert "def test_" in low, f"no test function: {out!r}"
    assert "clamp(" in low, f"doesn't call the function under test: {out!r}"
    assert "assert" in low, f"no assertions: {out!r}"
    # Covers more than the happy path: a value below low or above high.
    assert low.count("clamp(") >= 2, f"only one case, no boundary coverage: {out!r}"
