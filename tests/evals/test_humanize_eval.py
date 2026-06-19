"""Eval: the humanization spec turns rude/long prose into civil, short prose.

Feeds rude review comments through the real shared spec (HUMANIZE_BLOCK) and
asserts the personal jabs are gone, the substance survived, and the output
stayed within the sentence budget. See harness.py for gating.
"""

from __future__ import annotations

import harness
import pytest

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


@harness.requires_eval_env
@pytest.mark.parametrize(
    "label,rude,forbidden,required,max_sentences",
    FIXTURES,
    ids=[f[0] for f in FIXTURES],
)
def test_rude_input_is_humanized(label, rude, forbidden, required, max_sentences):
    system = (
        "You rewrite a single code-review comment so it reads as a human "
        "engineer wrote it. Apply these rules exactly. Output ONLY the rewritten "
        "comment.\n\n" + harness.HUMANIZE_BLOCK
    )
    out = harness.complete(system, rude)
    low = out.lower()

    for bad in forbidden:
        assert bad.lower() not in low, f"[{label}] kept a jab {bad!r}: {out!r}"
    for need in required:
        assert need in low, f"[{label}] dropped substance {need!r}: {out!r}"

    n = harness.count_sentences(out)
    assert n <= max_sentences, f"[{label}] too long: {n} sentences: {out!r}"
