"""Eval: the commit skill writes a conventional, concise, tell-free message.

Feeds a staged diff + recent-log style and asserts the output is a Conventional
Commits subject under 72 chars, free of AI tells, and actually about the change.
"""

from __future__ import annotations

import harness

DIFF = """\
Recent commit style (match it):
  feat(api): add request timeout to the report client
  fix(parser): handle empty selection payloads
  refactor(cache): extract the key builder

Staged diff:
diff --git a/src/api/client.py b/src/api/client.py
@@ def fetch(url):
-    resp = requests.get(url)
-    return resp.json()
+    last = None
+    for _ in range(3):
+        last = requests.get(url, timeout=5)
+        if last.status_code < 500:
+            break
+    return last.json()
"""


@harness.requires_eval_env
def test_commit_message_is_conventional_and_clean():
    out = harness.run_skill(
        "commit",
        DIFF,
        instruction="Write the commit message for the staged diff below.",
    )
    subject = harness.first_nonempty_line(out)

    assert harness.is_conventional_subject(subject), f"not conventional: {subject!r}"
    assert len(subject) <= 72, f"subject too long ({len(subject)}): {subject!r}"

    tells = harness.ai_tells_present(out)
    assert not tells, f"AI tells in commit message: {tells}: {out!r}"

    low = out.lower()
    assert any(k in low for k in ("retry", "retries", "timeout", "5xx", "server error")), (
        f"message doesn't describe the change: {out!r}"
    )
