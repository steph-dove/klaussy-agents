"""Agent eval for the prompt-side humanization spec (tone, not tells).

The deterministic scrubber is unit-tested elsewhere. The rude->civil rewrite,
though, is done by a model following `HUMANIZE_BLOCK`, so it can't be a plain
assertion — it needs a live model run. This harness feeds rude review comments
through the *actual shipped spec* and asserts the output (a) drops the personal
jabs and (b) keeps the substance.

It is opt-in and never runs in normal CI: it skips unless `KLAUSSY_RUN_EVALS=1`
and an Anthropic API key are both present. Run it locally with:

    KLAUSSY_RUN_EVALS=1 pytest tests/test_humanize_eval.py -v

Override the model with `KLAUSSY_EVAL_MODEL` (default: claude-sonnet-4-6).
"""

from __future__ import annotations

import os

import pytest

from klaussy.skills import HUMANIZE_BLOCK

# (label, rude input, forbidden substrings, required substance, max_sentences).
# Forbidden checks are case-insensitive; required checks are lowercased contains
# so the model can paraphrase freely as long as the meaning lands. max_sentences
# enforces the brevity rule (a single review comment stays within 1-5 sentences).
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


def _count_sentences(text: str) -> int:
    """Rough sentence count: terminal . ! ? runs, ignoring abbreviations enough for a bound."""
    import re

    return len([s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()])


def _run_spec(text: str, model: str) -> str:
    """Humanize `text` by calling a model with the shipped spec as the system prompt."""
    import anthropic

    client = anthropic.Anthropic()
    system = (
        "You rewrite a single code-review comment so it reads as a human "
        "engineer wrote it. Apply these rules exactly. Output ONLY the rewritten "
        "comment, nothing else.\n\n" + HUMANIZE_BLOCK
    )
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": text}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


@pytest.mark.skipif(
    os.environ.get("KLAUSSY_RUN_EVALS") != "1",
    reason="agent eval is opt-in; set KLAUSSY_RUN_EVALS=1 to run",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
@pytest.mark.parametrize(
    "label,rude,forbidden,required,max_sentences",
    FIXTURES,
    ids=[f[0] for f in FIXTURES],
)
def test_rude_input_is_humanized(label, rude, forbidden, required, max_sentences):
    pytest.importorskip("anthropic")
    model = os.environ.get("KLAUSSY_EVAL_MODEL", "claude-sonnet-4-6")
    out = _run_spec(rude, model)
    low = out.lower()

    for bad in forbidden:
        assert bad.lower() not in low, f"[{label}] kept a personal jab {bad!r}: {out!r}"
    for need in required:
        assert need in low, f"[{label}] dropped substance {need!r}: {out!r}"

    n = _count_sentences(out)
    assert n <= max_sentences, f"[{label}] too long: {n} sentences (>{max_sentences}): {out!r}"
