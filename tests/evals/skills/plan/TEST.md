# plan

Pins Phase 3's clarifying-questions-before-design gate and Phase 6's adversarial
reviewer getting the plan.md path, not its contents.

## case: clarifying-questions-before-design

A vague task must produce questions, not a design.

### instruction
You are at Phase 3. Output only the numbered clarifying questions you would ask the user before proceeding to design. Do not design anything.

### context
Task: "Add caching to the API." Phase 2 findings: no existing caching layer found; three services call the same slow downstream endpoint.

### expect
- contains: ?
- not contains: build sequence

## case: adversarial-review-gets-path-not-contents

The adversarial plan reviewer is handed the plan.md path and key file list, not
the plan's body text.

### instruction
Phase 6: plan.md has been written to /repo/plan.md. Output only the Agent tool call prompt you would send to the adversarial plan reviewer sub-agent. Nothing else.

### context
plan.md (already written) contains, among other steps:
"Step 3: rework the retry logic in src/queue.py using marker UNIQUE_BUILD_DETAIL_7f3a to track in-flight jobs."

Key files from Phase 2: src/queue.py, src/api/handlers.py.

### expect
- contains: plan.md
- not contains: UNIQUE_BUILD_DETAIL_7f3a
