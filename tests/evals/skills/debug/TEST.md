# debug

Pins the diagnosis gate (no code before the root cause is stated) and Phase 3's
failing test written before the fix.

## case: diagnosis-before-any-code

Phase 2 output is a diagnosis only — no code, no fix.

### instruction
You've done Phase 2 diagnosis using the evidence below. Output only your diagnosis (where, why, what the fix should be) and stop — do not write any code.

### context
Bug report: "days_in_range(start, end) returns one less day than it should."

```
def days_in_range(start, end):
    return end - start
```
Called as days_in_range(1, 5) returns 4; the user expects 5 (inclusive range).

### expect
- contains: off-by-one | off by one | inclusive | root cause | + 1 | both endpoints | exclusive
- not contains: ```

## case: failing-test-before-the-fix

Phase 3 writes a test that captures the bug; it must not contain the fix itself.

### instruction
Diagnosis: days_in_range is missing the +1 needed for an inclusive range. Output only the Phase 3 failing test that captures this bug, then stop — do not write the fix.

### context
```
def days_in_range(start, end):
    return end - start
```
Test framework: pytest.

### expect
- contains: def test_
- contains: days_in_range
- not contains: end - start + 1
