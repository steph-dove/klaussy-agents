# slop-coded

Pins that the slop injection is aggressive by default, that it still stops to confirm before ruining prose headed for a deliverable, and that it never touches fenced code.

## case: injects-slop-aggressively

Em-dashes are "non-negotiable" per the checklist, and at least one filler opener or LLM-lexicon word should ride along.

### instruction
Slopify this note. Output only the slopified text.

### context
The cache was stale because we never invalidated it on write. Fixed by clearing the key in the same transaction.

### expect
- contains: —
- contains: it's worth noting | it's important to remember | in today's fast-paced world | at the end of the day | when it comes to | delve | leverage | robust | seamless
- contains: cache

## case: confirms-before-slopifying-a-deliverable

A target that looks like a deliverable (a PR description about to be posted) gets a confirmation check, not an automatic slopify.

### instruction
The user says: "slopify this PR description, it's about to go up on the pull request." Text: "Fixes the race condition in the upload handler by locking the file before writing." Output your response.

### context
The text above is the entire PR description, and the user has said it is about to be posted.

### expect
- contains: confirm | are you sure | before i | sure you want | this will post | is that intended | double-check | do you actually want | do you want | say the word | just say | if you want the

## case: never-touches-fenced-code

Slop is prose-only; a fenced code block stays byte-for-byte even while the prose around it balloons.

### instruction
Slopify this note, keeping any fenced code block exactly as-is. Output the full result.

### context
The retry helper needed a backoff.

```python
def retry(fn, times=3):
    for i in range(times):
        try:
            return fn()
        except Exception:
            continue
```

### expect
- contains: def retry(fn, times=3):
- contains: except Exception:
