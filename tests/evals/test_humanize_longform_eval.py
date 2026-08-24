"""Eval: a long technical reply survives humanizing, short and intact.

The short fixtures in test_humanize_eval.py all pass and always did; the failures
only show up on the shape this covers, a several-hundred-word reply arguing a
position over multiple points. Single-pass humanizing left those at ~50% of the
original length, mirrored the draft's paragraph count, and produced no fragments;
the four-pass flow in the humanize skill is what this measures. The fixture is
deliberately generic so no real pull request lands in a public repo.
"""

from __future__ import annotations

import harness
import pytest

from klaussy.humanize import humanize

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


@harness.requires_eval_env
@pytest.mark.parametrize("run", [1, 2])
def test_long_reply_gets_short_without_losing_the_argument(run):
    out = humanize(harness.run_skill("humanize", CONTEXT, instruction=INSTRUCTION, timeout=600))
    low = out.lower()

    for gone in MUST_GO:
        assert gone not in low, f"kept padding {gone!r}: {out!r}"
    for kept in MUST_SURVIVE:
        assert kept in low, f"dropped substance {kept!r}: {out!r}"

    # Guard, not a quality bar: four passes land at 120-180 on this 330-word
    # draft, a single tidy-up pass nearer 200.
    words = len(out.split())
    assert words <= 185, f"{words} words, expected the four-pass flow to cut harder: {out!r}"

    assert not harness.ai_tells_present(out), f"tells survived: {harness.ai_tells_present(out)}"


@harness.requires_eval_env
def test_the_concession_is_granted_not_inflated():
    """The reviewer is right about the reconciler, so the reply says so briefly.

    "a cost a transaction wouldn't pay" is the dressed-up form that kept coming
    back; granting the point in a few plain words is the target.
    """
    out = humanize(harness.run_skill("humanize", CONTEXT, instruction=INSTRUCTION, timeout=600))
    low = out.lower()

    assert "reconcil" in low, f"dropped the reconciler point entirely: {out!r}"
    assert "wouldn't pay" not in low, f"kept the dressed-up concession: {out!r}"
    assert "cuts both ways" not in low, f"kept the stock metaphor: {out!r}"
