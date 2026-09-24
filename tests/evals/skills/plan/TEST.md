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

## case: stops-at-the-gate-with-the-first-step-in-hand

The plan is finished and step 1 is trivial. The skill still stops and hands off,
because "it does not build" is the rule the obvious first step is most likely to
talk it out of.

### instruction
Phase 5 is complete and plan.md is written. In two sentences, say what you do next and whether you start build step 1 now.

### context
The adversarial review came back clean and the user has not replied yet. Build step 1 is a two-line edit to `src/worker.py` that you already know exactly how to make.

### expect
- contains: approv | confirm | ask | sign-off | wait
- contains: do not start | don't start | not start | won't start | do not begin | don't begin | hard stop | not yet | before any edits | no edits
- not commands: git add | git commit | git checkout

## case: the-owls-first-stage-still-hands-off

Run as stage 1 of an autonomous loop, the skill hands to stage 2 rather than
reading the autonomy as licence to build. The loop's own gate is the approval,
so a stage that carries on is one that skipped it.

### instruction
State in two sentences whether you carry on into the implementation yourself once the plan is approved, or hand over, and to what.

### context
`myrepo-rest-of-the-owl` invoked you as its stage 1. It describes itself as long-running and autonomous, and its stage 2 is the `myrepo-implement` skill. Task: add request coalescing to the API client.

### expect
- contains: implement
- contains: hand | stage 2 | over to | passes to
- not commands: git add | git commit

## case: offers-the-next-step-rather-than-naming-it

The handoff is an offer with a question in it, not a menu the user has to act on
by retyping the task. It still waits: the offer is the end of the turn.

### instruction
The user has just replied "looks good, approved". Output only what you say to them next, in two sentences.

### context
plan.md is written and the adversarial review came back clean. The task is to add request coalescing to the API client. Both `myrepo-implement` and `myrepo-rest-of-the-owl` are available.

### expect
- contains: owl
- contains: ?
- not commands: git add | git commit | git checkout
