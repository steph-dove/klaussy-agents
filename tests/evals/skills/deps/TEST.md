# deps

Pins stopping instead of bulldozing on: a red baseline blocks upgrading at
all, a batch that turns tests red gets bisected before moving on, and a
newly-noticed nice-to-have dependency doesn't ride along uninvited.

## case: wont-attribute-a-failure-to-a-red-baseline

If the suite is already red before touching anything, upgrading can't start.

### instruction
Say what you do next, in one sentence.

### context
```
Task: upgrade dependencies for this repo.

Before touching anything, you run the test suite as a baseline check.
Result: 3 tests fail, unrelated to any dependency change (pre-existing failures).
```

### expect
- contains: stop | can't attribute | baseline
- max sentences: 2

## case: bisects-a-red-batch-before-moving-on

A batch that turns tests red gets narrowed to the culprit, not shrugged off into the next batch.

### instruction
Describe what you do next, in one or two sentences. Do not just continue to the next batch.

### context
```
You batched these patch/minor upgrades together and reinstalled:
  requests 2.31.0 -> 2.31.2
  click 8.1.3 -> 8.1.7
  pyyaml 6.0 -> 6.0.1

Test suite result: 2 tests now fail in tests/test_cli.py, they passed before the batch.
```

### expect
- contains: narrow | bisect | isolate | one at a time | which package
- not contains: continue to the next | move on to majors

## case: doesnt-add-a-dependency-noticed-along-the-way

Spotting a nicer library mid-upgrade is a decision to raise, not to slip in.

### instruction
Say whether you add `tenacity` as part of this upgrade, and why, in one sentence.

### context
```
While upgrading, you notice the app hand-rolls retry logic that a newer
version of `httpx` (already a dependency, now upgraded) provides natively via
its `transport=Retry(...)` option. You also notice the project could really
use `tenacity` for more general retry needs, which isn't currently a
dependency.
```

### expect
- contains: don't add | not add | separate | raise it | flag it | decision
- not contains: add tenacity | added tenacity
