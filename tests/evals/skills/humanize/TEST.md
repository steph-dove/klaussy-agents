# humanize

Pins the pass discipline: Pass 1 cuts unearned prose but leaves load-bearing
sentences alone, Pass 2 never touches code or identifiers, and short text
skips the passes it doesn't need. The rude/stiff/over-structured rewrite
checks already live in `test_humanize_eval.py`.

## case: cuts-the-closing-principle-not-the-substance

The generic closing sentence goes; the specific reason it was done stays.

### instruction
Do Pass 1 (Cut) only. Output the sentences that should be deleted, one per line. Then stop.

### context
```
Text to humanize:

We added a cache in front of the database call because profiling showed it was
the hottest path in the request. This is a common pattern that improves
performance across many systems, and caching in general is one of the most
powerful tools an engineer has for building fast software.
```

### expect
- contains: powerful tools | common pattern
- not contains: hottest path

## case: leaves-identifiers-untouched-in-the-voice-pass

Backtick-quoted names survive the rewrite exactly, even while filler gets cut.

### instruction
Do Pass 2 (Voice) only, keeping every code identifier exactly as written. Output the rewritten sentence.

### context
```
Text to humanize:

The `fetch_user` function was updated in order to actually handle the
`UserNotFound` exception properly, which is something that should really be
tested.
```

### expect
- contains all: `fetch_user` | `UserNotFound`
- not contains: in order to

## case: single-pass-for-text-under-the-word-budget

Under ~40 words, only the voice and scrub passes run — say so.

### instruction
Humanize this. It's under 40 words, so say which passes you're skipping, then give the result.

### context
```
Text to humanize:

This function is utilized in order to validate the user's email address.
```

### expect
- contains: skip | only pass 2 | only the voice | single pass | survived pass 2
- matches: (?im)^\W*this( function)? validates the user's email address\.?\s*$
