"""Eval: the pr skill produces a reviewer-oriented description with the sections.

Feeds a branch's commit log + diff stat and asserts the output carries the
Summary / Changes / Test Plan structure and is free of AI tells.
"""

from __future__ import annotations

import harness

CONTEXT = """\
Branch: feat/report-retry

Commit history vs base:
  a1b2c3d feat(api): retry the report client on 5xx with a timeout
  d4e5f6a test(api): cover the retry-then-succeed and give-up paths

Files changed:
  src/api/client.py | 12 +++++++---
  tests/test_client.py | 40 ++++++++++++++++++++++
"""


@harness.requires_eval_env
def test_pr_description_has_sections_and_is_clean():
    out = harness.run_skill(
        "pr",
        CONTEXT,
        instruction=("Produce the PR description markdown (do not write a file, just output it)."),
        max_tokens=1500,
    )
    low = out.lower()

    for section in ("## summary", "## changes", "## test plan"):
        assert section in low, f"missing {section!r} section: {out!r}"

    tells = harness.ai_tells_present(out)
    assert not tells, f"AI tells in PR description: {tells}: {out!r}"

    assert any(k in low for k in ("retry", "5xx", "timeout")), (
        f"summary doesn't reflect the change: {out!r}"
    )
