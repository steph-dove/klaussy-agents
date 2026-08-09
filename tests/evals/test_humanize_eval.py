"""Eval: the humanization spec turns rude/long/stiff prose into civil, short prose.

Feeds review comments through the real shared spec (HUMANIZE_BLOCK) and asserts
three things the spec claims to do: personal jabs go away and the substance
survives (rude fixtures), stiff written-up phrasing becomes spoken register
under a word budget (register fixtures), and structure a short comment doesn't
need gets flattened to prose (shape fixture). See harness.py for gating.
"""

from __future__ import annotations

import re

import harness
import pytest

from klaussy.humanize import humanize

# (label, rude input, forbidden substrings, required substance, max_sentences)
FIXTURES = [
    (
        "mocked-unit-tests",
        "Personally I don't find these unit tests useful, because you are "
        "mocking everything, so there is little left to test.\n\n"
        "I would prefer to use an e2e AVA test instead.\n\n"
        "See the tests for the chatbot and the tag groups for example.",
        ["you are mocking", "you forgot", "obviously", "personally"],
        ["mock", "e2e", "ava", "chatbot"],
        5,
    ),
    (
        "swallowed-exception",
        "This is a mess. Did you even run it? You're catching the exception "
        "and swallowing it, which is obviously wrong and hides real failures. "
        "Just rethrow it.",
        ["a mess", "did you even", "obviously", "you're catching"],
        ["exception", "rethrow"],
        5,
    ),
]


SYSTEM = (
    "You rewrite a single code-review comment so it reads as a human engineer "
    "wrote it. The comment is posted inline on the line it refers to, so the "
    "reader is already looking at that code. Apply these rules exactly. Output "
    "ONLY the rewritten comment.\n\n" + harness.HUMANIZE_BLOCK
)


@harness.requires_eval_env
@pytest.mark.parametrize(
    "label,rude,forbidden,required,max_sentences",
    FIXTURES,
    ids=[f[0] for f in FIXTURES],
)
def test_rude_input_is_humanized(label, rude, forbidden, required, max_sentences):
    out = harness.complete(SYSTEM, rude)
    low = out.lower()

    for bad in forbidden:
        assert bad.lower() not in low, f"[{label}] kept a jab {bad!r}: {out!r}"
    for need in required:
        assert need in low, f"[{label}] dropped substance {need!r}: {out!r}"

    n = harness.count_sentences(out)
    assert n <= max_sentences, f"[{label}] too long: {n} sentences: {out!r}"


# The word budget is what stops a rewrite from sounding nicer at the same length.
# (label, stiff input, forbidden phrasings, required substance, max_words)
REGISTER_FIXTURES = [
    (
        "verify-after-parse",
        "The handler performs full deserialization of the payload prior to "
        "verification of the signature, which may potentially expose the parser "
        "to untrusted input. It is recommended that signature verification be "
        "conducted first.",
        ["performs full deserialization", "prior to", "may potentially", "it is recommended"],
        ["signature"],
        40,
    ),
    (
        "stale-cache-read",
        "Prior to this change, invalidation of the cache was performed on every "
        "write operation. It is worth noting that the current implementation has "
        "the ability to serve stale data in the event that a concurrent writer "
        "commits first.",
        ["prior to", "it is worth noting", "has the ability to", "in the event that"],
        ["cache", "stale"],
        40,
    ),
]


@harness.requires_eval_env
@pytest.mark.parametrize(
    "label,stiff,forbidden,required,max_words",
    REGISTER_FIXTURES,
    ids=[f[0] for f in REGISTER_FIXTURES],
)
def test_stiff_input_becomes_spoken_register(label, stiff, forbidden, required, max_words):
    out = harness.complete(SYSTEM, stiff)
    low = out.lower()

    for bad in forbidden:
        assert bad.lower() not in low, f"[{label}] kept stiff phrasing {bad!r}: {out!r}"
    for need in required:
        assert need in low, f"[{label}] dropped substance {need!r}: {out!r}"

    words = len(out.split())
    assert words <= max_words, f"[{label}] over budget: {words} words: {out!r}"

    # Phrase tells are what the prompt controls; the em-dash is the scrubber's
    # job, so it's asserted on the scrubbed text (see test_explain_eval.py).
    phrase_tells = [t for t in harness.ai_tells_present(out) if t != "—"]
    assert not phrase_tells, f"[{label}] phrase tells survived: {phrase_tells}: {out!r}"
    assert not harness.ai_tells_present(humanize(out)), (
        f"[{label}] tells survive the deterministic scrubber: {out!r}"
    )


# A two-sentence point wearing a report's clothes. Structure is its own AI tell,
# independent of how the sentences read, so the spec's Shape rules have to strip
# it back to prose.
OVER_STRUCTURED = """\
## Review Finding

**Severity:** Medium
**Category:** Correctness
**Location:** `src/jobs/export.py:212`

**What the issue is:**
- The cleanup call is not awaited before the function returns.

**Why it matters:**
- The temp directory can be removed while the export is still writing to it.

**Recommended fix:**
- Await the cleanup coroutine after the writes complete.

Let me know if you'd like me to elaborate on any of these points!
"""


@harness.requires_eval_env
def test_over_structured_comment_is_flattened_to_prose():
    out = harness.complete(SYSTEM, OVER_STRUCTURED)
    low = out.lower()

    assert "await" in low, f"dropped substance: {out!r}"
    assert any(k in low for k in ("temp", "cleanup")), f"dropped the failure mode: {out!r}"

    assert not re.search(r"^\s*#", out, re.MULTILINE), f"kept a heading: {out!r}"
    assert not re.search(r"^\s*[-*]\s", out, re.MULTILINE), f"kept a bullet list: {out!r}"
    assert not re.search(r"^\s*\*\*[^*]+:\*\*", out, re.MULTILINE), f"kept field labels: {out!r}"
    assert not harness.ai_tells_present(out), f"kept tells: {harness.ai_tells_present(out)}"

    n = harness.count_sentences(out)
    assert n <= 3, f"over the review-comment budget: {n} sentences: {out!r}"
