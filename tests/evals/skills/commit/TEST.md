# commit

Pins skipping the body on a trivial change and pulling the ticket reference
from the branch name. Subject/tells/relevance are already covered by
`test_commit_eval.py`.

## case: skips-body-when-subject-says-it-all

A version bump needs one line, not an invented body.

### instruction
Write the commit message for the staged diff below. Output ONLY the commit message.

### context
```
Recent commit style (match it):
  fix(readme): correct install command typo
  chore(deps): bump lodash to 4.17.21

Staged diff:
diff --git a/package.json b/package.json
@@
-  "version": "1.2.2",
+  "version": "1.2.3",
```

### expect
- conventional subject
- max lines: 1

## case: includes-ticket-reference-from-branch-name

The branch's ticket ID belongs in the body.

### instruction
Write the commit message for the staged diff below.

### context
```
Current branch: feat/FEAT-482-export-csv

Recent commit style (match it):
  feat(export): add CSV button to reports page

Staged diff:
diff --git a/src/export/csv.py b/src/export/csv.py
@@
+def export_csv(rows):
+    writer = csv.writer(sys.stdout)
+    writer.writerows(rows)
+    return True
```

### expect
- conventional subject
- contains: feat-482

## case: body-explains-why-for-a-non-obvious-fix

A race-condition fix earns a body that says why, not what.

### instruction
Write the commit message for the staged diff below. Output ONLY the commit message.

### context
```
Recent commit style (match it):
  fix(worker): guard against duplicate job dispatch

Staged diff:
diff --git a/src/worker/queue.py b/src/worker/queue.py
@@ def dequeue(self):
-    job = self.jobs.pop(0)
-    return job
+    with self.lock:
+        if not self.jobs:
+            return None
+        return self.jobs.pop(0)
```

### expect
- conventional subject
- contains: race | lock | concurrent | duplicate | thread-safe
