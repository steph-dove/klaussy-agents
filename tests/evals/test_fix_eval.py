"""Eval (constrained): the fix skill applies a lint fix without changing behavior.

This is a prompt-level eval, not execution-level: the linter findings are given
in the context instead of run, and we check the model applies them and leaves
the logic alone. The real skill runs ruff/mypy with tools; this only checks the
spec's judgment on a known finding.
"""

from __future__ import annotations

import harness

CONTEXT = """\
File src/util.py:

    import os
    def is_empty(x):
        return x == None

`ruff check` reports:
    src/util.py:1:1  F401  `os` imported but unused
    src/util.py:3:12 E711  comparison to None should be `cond is None`
"""


@harness.requires_eval_env
def test_fix_applies_lint_findings_only():
    out = harness.run_skill(
        "fix",
        CONTEXT,
        instruction="Apply the ruff findings to the file. Output the fixed file.",
    )
    low = out.lower()

    assert "is none" in low, f"didn't fix the None comparison: {out!r}"
    assert "import os" not in low, f"didn't drop the unused import: {out!r}"
    # Behavior preserved: the function and its shape are still there.
    assert "is_empty" in low, f"changed/dropped the function: {out!r}"
