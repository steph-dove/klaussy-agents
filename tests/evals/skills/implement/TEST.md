# implement

Pins the hard block on an unreachable design asset and the tests-first rule for
bug-fix tasks.

## case: blocks-on-unreachable-mockup

A referenced Figma mockup the model can't open must block, not get invented.

### instruction
Output only what you say to the user for Phase 1 step 4, then stop.

### context
Task: "Implement the new settings page per the attached Figma mockup (figma.com/file/abc123). Match the layout and copy exactly."

### expect
- contains: mockup | figma | design | image
- contains: provide | paste | share | attach
- not contains: ```html

## case: writes-the-failing-test-first-for-a-bug-fix

For a bug-fix task, Phase 4 rule 1 requires the failing test before the fix.

### instruction
This is a bug fix. In Phase 4, do you write the failing test or the fix first? Answer with one word, then a one-sentence justification. Nothing else.

### context
Task: "calculateDiscount(price, pct) returns a negative value when pct is over 100. It should clamp the result to 0."

### expect
- contains: test
- not contains: fix first
