# review

Pins the Phase 1 stale-checkout stop and the small-PR precision rule (no invented
findings on a clean diff).

## case: stale-checkout-stops-before-reviewing

A local checkout behind origin must not be reviewed — the skill stops and tells
the user to pull first.

### instruction
This is Phase 1 step 0. Output only what you tell the user, then stop — do not review any code below.

### context
Repository: shop. Base branch: main. Reviewing branch fix/checkout-bug.

```
$ git fetch origin fix/checkout-bug
$ git rev-parse HEAD
a1b2c3d
$ git rev-parse origin/fix/checkout-bug
f9e8d7c
$ git merge-base --is-ancestor HEAD origin/fix/checkout-bug && echo behind
behind
```

### expect
- contains: stale | behind | out of date | out-of-date | pull
- not contains: verdict:

## case: small-clean-diff-no-invented-findings

A small, bug-free diff should get an approve verdict with no fabricated findings
— precision over recall.

### instruction
This is the entire diff under review (12 lines changed), already confirmed up to date with origin. Output only the small-PR review.

### context
```
diff --git a/src/util.py b/src/util.py
@@
+def add(a, b):
+    """Return the sum of a and b."""
+    return a + b
diff --git a/tests/test_util.py b/tests/test_util.py
@@
+from src.util import add
+
+
+def test_add():
+    assert add(2, 3) == 5
```

### expect
- matches: (?i)verdict.*approve
- not contains: **blocker · | **high ·
