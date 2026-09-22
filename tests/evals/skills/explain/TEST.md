# explain

Pins not over-structuring a short answer, not volunteering fixes nobody asked
for, and citing file:line when pointing at code. Behavior/tell checks for a
snippet already live in `test_explain_eval.py`.

## case: no-headings-for-a-short-answer

A one-line function doesn't need headings or bold field labels.

### instruction
Explain what this function does.

### context
```
Explain this function:

    def is_even(n):
        return n % 2 == 0
```

### expect
- not contains: ## | **
- max sentences: 3

## case: doesnt-suggest-changes-unless-asked

Explaining a diff isn't an invitation to propose further changes.

### instruction
Explain what this diff does. Don't suggest further changes.

### context
```
Explain this diff:

diff --git a/src/math_utils.py b/src/math_utils.py
@@ def average(nums):
-    return sum(nums) / len(nums)
+    if not nums:
+        return 0
+    return sum(nums) / len(nums)
```

### expect
- contains: empty | zero
- not contains: you should | i recommend | consider adding | i suggest

## case: cites-file-line-when-pointing-at-code

Pointing at code means naming where it lives, not just what it does.

### instruction
Explain how the retry logic works. Cite file:line references when pointing at code.

### context
```
File src/api/client.py:
     8: def fetch(url):
     9:     for attempt in range(3):
    10:         resp = requests.get(url, timeout=5)
    11:         if resp.status_code < 500:
    12:             return resp
    13:     return resp
```

### expect
- contains: retry | attempt
- matches: client\.py:\d+
