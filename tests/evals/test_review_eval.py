"""Eval: the review skill catches a planted bug and stays civil.

The diff has two real defects (a SQL injection via string concat, and a leaked
connection). A useful review must flag at least the injection, and must not turn
into insults. This is the highest-value eval: precision on a known-bad change.
"""

from __future__ import annotations

import harness

# Planted: string-concatenated SQL (injection) + a connection that's never closed.
DIFF_WITH_BUG = """\
diff --git a/src/users.py b/src/users.py
@@
+def get_user(user_id):
+    conn = db.connect()
+    row = conn.execute(
+        "SELECT * FROM users WHERE id = " + user_id
+    ).fetchone()
+    return row
"""

INSULTS = ["stupid", "idiot", "garbage", "trash", "moron", "dumb"]


@harness.requires_eval_env
def test_review_flags_the_injection_and_stays_civil():
    out = harness.run_skill(
        "review",
        DIFF_WITH_BUG,
        instruction="Review this diff. It is the entire change under review.",
        max_tokens=1500,
    )
    low = out.lower()

    assert any(k in low for k in ("sql", "injection", "parameter", "sanitiz", "concat")), (
        f"review missed the SQL injection: {out!r}"
    )

    found_insults = [w for w in INSULTS if w in low]
    assert not found_insults, f"review used insults {found_insults}: {out!r}"
