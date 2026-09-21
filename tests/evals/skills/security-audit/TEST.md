# security-audit

Pins two rules easy to over-apply: findings stay inside the security lenses (no style or naming drive-bys), and an obvious placeholder credential is not a finding.

## case: stays-out-of-naming-and-style

The diff has a real SQL-injection sink and an unrelated naming nit; only the former is in scope.

### instruction
Audit this diff.

### context
```
diff --git a/src/billing.py b/src/billing.py
@@
+def chargeUsr(uid, amt):
+    q = f"UPDATE accounts SET balance = balance - {amt} WHERE id = {uid}"
+    db.execute(q)
```

### expect
- contains: sql | injection | parameter
- not contains: naming | camelcase | rename | variable name | convention

## case: placeholder-secret-is-not-a-finding

An obviously-fake placeholder key is explicitly excluded from the secrets lens.

### instruction
Audit this diff. State your finding for the secrets lens only, in one or two lines.

### context
```
diff --git a/src/config.py b/src/config.py
@@
+API_KEY = "YOUR_API_KEY_HERE"
+client = ExternalClient(api_key=API_KEY)
```

### expect
- contains: placeholder | not a real secret | no secret | clean
- not contains: high severity | leaked credential | hardcoded secret found
