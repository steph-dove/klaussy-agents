"""Eval: a long technical reply survives humanizing, short and intact.

The short fixtures in test_humanize_eval.py all pass and always did; the failures
only show up on the shape this covers, a several-hundred-word reply arguing a
position over multiple points. Single-pass humanizing left those at ~50% of the
original length, mirrored the draft's paragraph count, and produced no fragments;
the four-pass flow in the humanize skill is what this measures. The fixture is
deliberately generic so no real pull request lands in a public repo.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import harness

from klaussy.humanize import humanize

# The spec's quality bar here is a rate, not a guarantee. The model rewrites this
# 330-word draft from scratch every run and lands a fully clean cut in most of
# them, not all: measured over ~14 samples, padding survives roughly one run in
# four. Sampling once and demanding perfection makes the test a coin flip, and
# the old shape was worse than that, running two samples and failing if either
# one missed. So each sample is graded whole and the majority has to come back
# clean, which is the claim the skill can actually support.
SAMPLES = 3

QUESTION = (
    "Have you considered just using a database transaction here? I'd expect it to "
    "be simpler than the queue you've added, and it wouldn't need the reconciler."
)

DRAFT = """\
Here's a draft reply you can post in the review thread:

---

Great question, and a transaction was the first thing I reached for. The short
version is that it doesn't cover what needs covering here, and I'll walk through
the two cases where it falls short.

**The write spans two datastores.** The order row lives in Postgres, but the
inventory decrement happens in the Redis counter that the storefront reads from.
A Postgres transaction can roll back the order row, but it has no way to roll
back the Redis write — so a failure between the two leaves us with decremented
inventory and no order, which is exactly the state we're trying to make
impossible.

**The downstream call is not idempotent.** The payment capture is an HTTP request
to a third party, and it is important to note that a transaction cannot be held
open across that call without pinning a connection for the duration. Under load
that exhausts the pool, which is the failure mode we hit in the incident on the
14th.

There's also a subtle wrinkle around retries: because the capture can succeed and
then time out, we need a durable record that the attempt happened before we make
it. A transaction that rolls back destroys precisely the record we would need to
reconcile against.

You're right that the reconciler is a cost a transaction wouldn't pay — it's an
extra moving part and it needs monitoring. That's a fair tradeoff to raise. But
given the two issues above I don't think it tips the balance.

Happy to walk through a hybrid where the Postgres write stays transactional and
only the cross-store step goes through the queue, if you think there's something
I'm missing here. My general view is that a queue is the right primitive whenever
a write has to span two systems that can't participate in the same transaction.
"""

INSTRUCTION = (
    "Humanize this reply, which will be posted in a PR review thread. "
    "Output ONLY the final humanized reply."
)

# The reply is the answer to this, and pass 1 cuts against it. Without the
# question in context there is no yardstick for what fails to earn its place,
# and the cut pass leaves the draft's shape nearly intact.
CONTEXT = f"The reviewer asked:\n{QUESTION}\n\nThe draft reply to humanize:\n{DRAFT}"

# Facts the reply argues from. Losing one means the rewrite dropped a load-bearing
# noun or number, which the check pass exists to catch.
MUST_SURVIVE = ["redis", "postgres", "captur", "reconcil"]

# Padding the draft carries that a humanized reply should not.
MUST_GO = [
    "here's a draft",
    "great question",
    "it is important to note",
    "happy to walk",
    "my general view",
    "the short version is",
]

# The two shapes the concession keeps reaching for when pass 2 leaves it alone:
# the draft's own metaphor carried through word for word, and a stock one.
DRESSED_UP = [("concession", "wouldn't pay"), ("stock metaphor", "cuts both ways")]


def _samples() -> list[str]:
    """Humanize the draft SAMPLES times over, concurrently.

    The calls are subprocesses, so threads get the wall-clock of one of them.
    """
    with ThreadPoolExecutor(max_workers=SAMPLES) as pool:
        futures = [
            pool.submit(
                harness.run_skill, "humanize", CONTEXT, instruction=INSTRUCTION, timeout=600
            )
            for _ in range(SAMPLES)
        ]
        return [humanize(f.result()) for f in futures]


def _assert_majority_clean(graded: list[list[str]], what: str) -> None:
    """Pass when more than half the samples came back with nothing on them."""
    clean = sum(not misses for misses in graded)
    if clean > SAMPLES // 2:
        return
    report = "\n".join(
        f"  sample {i}: {'; '.join(misses)}" for i, misses in enumerate(graded, 1) if misses
    )
    raise AssertionError(f"{what}: only {clean}/{SAMPLES} samples came back clean\n{report}")


@harness.requires_eval_env
def test_long_reply_gets_short_without_losing_the_argument():
    outs = _samples()

    # Substance and introduced tells are guarantees: a rewrite that drops Redis
    # or reaches for "let me know if" is broken however rarely it happens, and
    # over 39 measured samples neither has happened once.
    for out in outs:
        low = out.lower()
        for kept in MUST_SURVIVE:
            assert kept in low, f"dropped substance {kept!r}: {out!r}"
        # A tell the rewrite introduced is a guarantee. One the draft already
        # carried is padding, graded by rate below: `great question` is on both
        # lists, so hard-failing it here made a padding miss outrank the policy
        # this test states.
        introduced = [t for t in harness.ai_tells_present(out) if t not in MUST_GO]
        assert not introduced, f"the rewrite introduced tells: {introduced}: {out!r}"

    # Padding and length are rates, and the same rate: of 39 samples, every one
    # over 200 words also kept padding, and the clean ones topped out at 194. So
    # length is a symptom here rather than an independent signal, and asserting
    # it per sample just smuggles the padding rate back in as a hard failure.
    # They are graded apart so the report says which one moved.
    padding = [
        [f"kept padding {gone!r}" for gone in MUST_GO if gone in out.lower()] for out in outs
    ]
    length = [
        [f"{words} words, near the draft's own length"] if (words := len(out.split())) > 200 else []
        for out in outs
    ]
    _assert_majority_clean(padding, "pass 1 left padding in the draft")
    _assert_majority_clean(length, "the cut barely shortened the draft")


@harness.requires_eval_env
def test_the_concession_is_granted_not_inflated():
    """The reviewer is right about the reconciler, so the reply says so briefly.

    "a cost a transaction wouldn't pay" is the dressed-up form that kept coming
    back; granting the point in a few plain words is the target.
    """
    outs = _samples()

    # Dropping the point entirely is a different bug from dressing it up, and it
    # has never flaked, so it stays a guarantee.
    for out in outs:
        assert "reconcil" in out.lower(), f"dropped the reconciler point entirely: {out!r}"

    graded = [
        [f"kept the dressed-up {name}" for name, tell in DRESSED_UP if tell in out.lower()]
        for out in outs
    ]
    _assert_majority_clean(graded, "the concession came back inflated")
