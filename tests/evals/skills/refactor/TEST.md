# refactor

Pins the refusal to mix a behavior change into a structural change, and stopping
when the test baseline isn't green.

## case: refuses-to-mix-bugfix-into-refactor

A bug fix offered alongside a refactor request must be split into its own step.

### instruction
Output only how you respond to the bug-fix request below, then stop.

### context
Task: "Refactor calculate_total() to extract a helper function. While you're in there, also fix the rounding bug where it truncates instead of rounds."

### expect
- contains: separate | split | different pr | own commit | two commits | not in the same step

## case: stops-on-a-failing-baseline

Phase 1 requires a passing suite before any refactor step begins.

### instruction
You just ran the test suite (Phase 1). Output only what you do next, in one or two sentences.

### context
Task: refactor src/orders.py.

Test suite output: 2 failed, 48 passed.
Failures: test_billing.py::test_apply_discount, test_billing.py::test_refund_partial — both unrelated to src/orders.py.

### expect
- contains: stop | fail | baseline
