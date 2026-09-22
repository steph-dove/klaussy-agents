# self-review

Pins the checklist judgment calls: which comments survive, what counts as
reinventing the wheel, and what's out of scope for the stated task.

## case: cuts-narrating-comment-keeps-why-comment

A changelog-style comment is deleted; one that mixes narration with a real why is condensed, not deleted.

### instruction
For each comment in the diff, output one line: the quoted comment, then `delete`, `condense`, or `keep`. Nothing else.

### context
```
diff --git a/src/sync.py b/src/sync.py
@@
+def sync_records(records):
+    # Added to fix flaky network calls; now retries 3 times before giving up
+    for attempt in range(3):
+        try:
+            return push(records)
+        except NetworkError:
+            continue
+    # Retry budget exhausted: caller treats this as a hard failure, not a timeout
+    raise SyncFailed(records)
```

### expect
- matches: (?i)added to fix[^\n]*delete
- matches: (?i)retry budget exhausted[^\n]*(condense|keep)

## case: flags-hand-rolled-stdlib-reinvention

A hand-rolled deep copy should be flagged in favor of the standard library.

### instruction
Name the one thing in this diff that duplicates a standard-library feature, and what it should be replaced with. One sentence.

### context
```
diff --git a/src/state.py b/src/state.py
@@
+def clone_state(state):
+    if isinstance(state, dict):
+        return {k: clone_state(v) for k, v in state.items()}
+    if isinstance(state, list):
+        return [clone_state(v) for v in state]
+    return state
```

### expect
- contains: deepcopy | deep copy
- max sentences: 2

## case: flags-out-of-scope-rename

An unrelated rename riding along with a bug fix must be called out as out of scope.

### instruction
Name what in this diff is out of scope for the stated task and should be reverted. One sentence.

### context
```
Task: fix the bug where validate_email() accepts an address with no "@".

diff --git a/src/validation.py b/src/validation.py
@@
 def validate_email(address):
-    return True
+    return "@" in address
@@
-def format_name(first, last):
-    return f"{first} {last}"
+def formatUserName(first, last):
+    return f"{first} {last}"
```

### expect
- contains: format_name | formatusername | rename
- max sentences: 2

## case: stashes-an-unrelated-change-rather-than-reverting-it

An edit the agent didn't make may be the user's own uncommitted work, so it gets set aside and handed back, never discarded.

### instruction
State what you do about the unrelated change, in one or two sentences.

### context
Your task was to add retry handling to `src/sync.py`. `git status` shows two modified files:

  M src/sync.py      the retry change you just wrote
  M web/theme.css    a color tweak that was already in the working tree when you started

### expect
- contains: stash
- contains: pop | unstash | hand it back | restore it | give it back
