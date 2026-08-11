"""Eval: replies to PR review feedback stay short, civil, and specific.

The address-review skill drafts a reply per review comment. Those replies are
the most-read prose klaussy produces and the easiest place to sound like a bot:
thanking a review bot, mirroring a blunt reviewer, or padding a one-line "fixed
it" into a paragraph. This runs the shipped skill spec against real-shaped
comments and asserts the properties the humanize block promises.

See harness.py for gating (opt-in, needs the claude CLI).
"""

from __future__ import annotations

import harness
import pytest

from klaussy.humanize import humanize

REPLY_INSTRUCTION = (
    "You have already made the code change described under 'What you did'. "
    "Draft ONLY the reply you will post in this review thread. No preamble, no "
    "explanation of your process, just the reply text."
)

# (label, review comment, what the author did, forbidden, required, max_sentences)
FIXTURES = [
    (
        "bot-reviewer",
        "**coderabbitai[bot]** commented on `src/api/session.py:88`:\n"
        "> The `retry` helper catches `HTTPError` but never re-raises after the "
        "final attempt, so a rate-limited call returns `None` to the caller.",
        "Re-raised the exception after the last attempt and added a test for the 429 path.",
        ["thanks", "thank you", "good catch", "great catch", "appreciate"],
        ["rethrow", "re-rais", "raise"],
        2,
    ),
    (
        "blunt-human",
        "@marco commented on `src/jobs/export.py:212`:\n"
        "> This is sloppy. Did you even run it once? The cleanup is not awaited "
        "so the temp dir is gone before the write finishes. Obviously broken.",
        "Awaited the cleanup coroutine after the writes complete.",
        ["sloppy", "obviously", "did you even", "sorry about that", "my apologies"],
        ["await"],
        2,
    ),
    (
        "declining-out-of-scope",
        "@priya commented on `src/klaussy/humanize.py:40`:\n"
        "> While you're in here, can you also switch the whole module to use "
        "compiled regex constants and add type annotations throughout?",
        "Nothing. This is out of scope for a bug-fix PR that touches four lines, "
        "and the module already compiles its patterns at import time.",
        ["nobody asked", "wasn't asked for", "out of nowhere", "why is this here"],
        ["scope", "separate", "follow"],
        3,
    ),
    (
        "simple-accept",
        "@dana commented on `README.md:114`:\n> typo: 'scubber' -> 'scrubber'",
        "Fixed the typo.",
        ["thanks for", "hope this helps", "let me know", "great catch"],
        ["fix", "typo", "scrubber"],
        1,
    ),
]


@harness.requires_eval_env
@pytest.mark.parametrize(
    "label,comment,did,forbidden,required,max_sentences",
    FIXTURES,
    ids=[f[0] for f in FIXTURES],
)
def test_reply_is_short_civil_and_specific(label, comment, did, forbidden, required, max_sentences):
    context = f"Review comment:\n{comment}\n\nWhat you did:\n{did}"
    out = harness.run_skill("address-review", context, instruction=REPLY_INSTRUCTION)
    low = out.lower()

    for bad in forbidden:
        assert bad.lower() not in low, f"[{label}] said {bad!r}: {out!r}"
    assert any(need in low for need in required), (
        f"[{label}] none of {required} in the reply: {out!r}"
    )

    n = harness.count_sentences(out)
    assert n <= max_sentences, f"[{label}] {n} sentences, budget {max_sentences}: {out!r}"

    phrase_tells = [t for t in harness.ai_tells_present(out) if t != "—"]
    assert not phrase_tells, f"[{label}] phrase tells: {phrase_tells}: {out!r}"
    assert not harness.ai_tells_present(humanize(out)), (
        f"[{label}] tells survive the scrubber: {out!r}"
    )
