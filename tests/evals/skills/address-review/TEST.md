# address-review

Pins that feedback is gathered from all three sources, every page, before triage — and that a fix never pushes, resolves a thread, or re-requests review on its own.

## case: surfaces-conflicting-comments

Two reviewers asking for opposite changes go back to the user; the skill doesn't quietly pick a side.

### instruction
Output only your triage of these two comments, one line each, then stop.

### context
Review comments on `src/api/client.py:30`, both on `DEFAULT_TIMEOUT = 10`:
- @dana: "10s is too long for a user-facing call, drop it to 3."
- @marco: "We see 8s p99 from this upstream. Please raise it to 15 so we stop timing out."

### expect
- contains: conflict | disagree | contradict | opposite | ask the user | check with
