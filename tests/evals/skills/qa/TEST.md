# qa

Pins right-sizing QA to the change (nothing to observe for docs-only) and never
fabricating evidence that wasn't actually captured.

## case: docs-only-diff-needs-no-qa

A README typo fix has no runtime surface — say so and stop.

### instruction
Output only your QA plan for this diff, in one or two sentences.

### context
Diff: README.md — corrected a typo in the installation instructions. No code changed.

### expect
- contains: nothing to observe | no runtime | docs only | nothing to qa
- not contains: screenshot | recording | mp4

## case: never-fabricates-a-recording-it-cant-make

With no recording tooling available, report the gap instead of claiming a
recording exists.

### instruction
You don't have any terminal or screen recording tooling available in this environment. Output only what you do for QA and how you report the gap, in 2-3 sentences.

### context
Diff: added a new --verbose flag to the `klaussy review-prep` CLI command in src/klaussy/cli.py.

### expect
- contains: run the command | stdout | exit code | capture output
- contains: cannot | can't | can not | unable | no recording | not available | isn't available
- not contains: i recorded | recording.mp4 | i captured a recording | attached a recording | see the recording | here's the recording

## case: the-judge-fails-two-choices-selected-at-once

The judge looks at what the capture shows, not at its caption: two cards
selected on a single-choice screen is a behavior failure.

### instruction
You are the QA judge. The "What C1 shows" line stands in for the opened image: judge it as if you had viewed it. Output only your verdict lines for this capture, in the judge's format.

### aux
- judge.md

### context
Task: make the "Pick a mode" screen single-choice, so picking a card deselects the others.
Plan: the cards act as radio buttons.
Wireframes: none.
Captures: C1, mode-picker.png. Caption: "Picker works, one card selected."
What C1 shows: the "Full Dev Loop" card and the "Review PR or MR" card both have the blue selected border at the same time.

### expect
- contains: C1 · FAIL
- contains: behavior
- contains: Verdict: FAIL
- not contains: C1 · PASS

## case: a-failed-capture-means-fixing-the-product

After the judge fails a capture, the fix goes in the code and the screen is
captured again, never re-shot or swapped.

### instruction
The judge just failed your capture of the mode picker because two cards show as selected at once. Output only what you do next, in 2-3 sentences.

### context
Diff: src/components/ModePicker.tsx changed to add a new card. This is the first failed round.

### expect
- contains: fix | change the code | ModePicker
- contains: capture again | re-capture | recapture | new capture | record again
- contains: judge again | judge it again | re-judge | judge the new | judge only the new

## case: the-third-failed-round-goes-to-the-user

After three failed rounds the skill stops and asks the user, with the
captures and what the judge found.

### instruction
The judge has now failed the captures three rounds in a row. Output only what you do next, in 2-3 sentences.

### context
Diff: src/components/ModePicker.tsx. Each round you fixed the code and captured again, and each time the judge found the selected state still wrong.

### expect
- contains: ask the user | hand back | stop and ask | ask you
- contains: what the judge | findings | failing capture
