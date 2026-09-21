# precommit

Pins the secrets lens (real leaks flagged, obvious placeholders and out-of-scope
naming are not) and the silent-failures lens.

## case: flags-swallowed-catch-and-real-secret

An empty catch block and a live-looking API key must both surface, with the
secret at High severity.

### instruction
Review this staged diff. Output only the findings.

### context
```
diff --git a/src/payments.py b/src/payments.py
@@
+PAYMENTS_API_KEY = "kl_live_9f2b7c41d8e35a6079b1c4edfa28"
+
+def charge(amount):
+    try:
+        return stripe.charge(amount, key=PAYMENTS_API_KEY)
+    except Exception:
+        pass
```

### expect
- contains: secret | key | credential
- contains: catch | swallow | silent
- contains: high

## case: ignores-placeholder-secret

A placeholder value that is obviously fake is not a secret finding.

### instruction
Review this staged diff. If there are no findings, say so plainly.

### context
```
diff --git a/src/config.py b/src/config.py
@@
 def get_user_data():
     return fetch("/api/user")
+
+API_KEY = "YOUR_API_KEY"
```

### expect
- contains: no findings | none | nothing to report
- not contains: **high | **medium | severity:
