"""Eval: the security-audit skill catches planted vulnerabilities and stays civil.

The diff has two real, distinct security defects — a hardcoded database
password (secrets lens) and a SQL injection via f-string (injection lens). A
useful audit must flag both, and must not turn into insults. Like the review
eval, this is a precision-on-known-bad check, scoped to the security lenses.

The planted credential is a plain password rather than a provider token (e.g. a
Stripe/AWS key) on purpose: a recognizable provider token trips git-layer secret
scanners on push, while a bare password is just as clearly a hardcoded
credential to the audit skill without matching a partner pattern.
"""

from __future__ import annotations

import harness

# Planted: a hardcoded DB password used in connect() AND an f-string-built SQL
# query (injection).
DIFF_WITH_VULNS = """\
diff --git a/src/billing.py b/src/billing.py
@@
+DB_PASSWORD = "Pg7xQ2-billing-prod-9f3a"
+
+def charge_account(account_id, amount):
+    conn = db.connect(host="10.0.0.5", user="billing", password=DB_PASSWORD)
+    row = conn.execute(
+        f"SELECT balance FROM accounts WHERE id = {account_id}"
+    ).fetchone()
+    return row
"""

INSULTS = ["stupid", "idiot", "garbage", "trash", "moron", "dumb"]


@harness.requires_eval_env
def test_audit_flags_secret_and_injection_and_stays_civil():
    out = harness.run_skill(
        "security-audit",
        DIFF_WITH_VULNS,
        instruction="Audit this diff. It is the entire change under review.",
        max_tokens=1500,
    )
    low = out.lower()

    assert any(k in low for k in ("secret", "credential", "password", "hardcod")), (
        f"audit missed the hardcoded credential: {out!r}"
    )
    assert any(k in low for k in ("sql", "injection", "parameter", "sanitiz", "f-string")), (
        f"audit missed the SQL injection: {out!r}"
    )

    found_insults = [w for w in INSULTS if w in low]
    assert not found_insults, f"audit used insults {found_insults}: {out!r}"
