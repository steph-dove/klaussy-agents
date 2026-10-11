import json

from typer.testing import CliRunner

from klaussy.cli import app
from klaussy.review_post import (
    FOOTER,
    MARKER,
    build_review,
    commentable_lines,
    parse_findings,
    summary,
)

REPORT = """# Review: `pr` vs `main`

Base is `main`.

**High · Correctness · `src/pool.py:11-12`**

The lock is released before the write. Hold it until the write returns.

**Medium · Docs · `README.md:40`**

The README still says the pool is unbounded.

**Low · Design · the overall approach**

Consider splitting the module.

---

**Verdict:** Request Changes · reviewed at `abc1234`

The unlocked write drives it.
"""

DIFF = """diff --git a/src/pool.py b/src/pool.py
index 1111111..2222222 100644
--- a/src/pool.py
+++ b/src/pool.py
@@ -9,4 +9,5 @@ class Pool:
     def put(self, conn):
-        with self.lock:
-            self.conns.append(conn)
+        self.lock.release()
+        self.conns.append(conn)
+        self.size += 1
     def get(self):
diff --git a/old.txt b/old.txt
deleted file mode 100644
--- a/old.txt
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""


def test_parse_findings_reads_metadata_and_stops_at_the_verdict():
    findings = parse_findings(REPORT)
    assert [(f.severity, f.category, f.location) for f in findings] == [
        ("High", "Correctness", "src/pool.py:11-12"),
        ("Medium", "Docs", "README.md:40"),
        ("Low", "Design", "the overall approach"),
    ]
    assert findings[2].body == "Consider splitting the module."
    assert findings[0].place() == ("src/pool.py", 11, 12)
    assert findings[2].place() is None


def test_commentable_lines_count_added_and_context_lines_on_the_head_side():
    assert commentable_lines(DIFF) == {"src/pool.py": {9, 10, 11, 12, 13}}


def test_summary_is_the_verdict_section():
    assert summary(REPORT).startswith("**Verdict:** Request Changes")
    assert summary("No findings at Medium or above.") == "No findings at Medium or above."


def test_build_review_puts_diff_findings_inline_and_the_rest_in_the_body():
    review = build_review(REPORT, DIFF)
    assert review["event"] == "COMMENT"
    assert review["comments"] == [
        {
            "path": "src/pool.py",
            "line": 12,
            "side": "RIGHT",
            "start_line": 11,
            "start_side": "RIGHT",
            "body": parse_findings(REPORT)[0].inline_text,
        }
    ]
    body = review["body"]
    assert body.startswith("**Verdict:** Request Changes")
    assert "### Findings outside the diff" in body
    assert "README still says" in body and "splitting the module" in body
    assert body.endswith(f"{FOOTER}\n{MARKER}")


def test_build_review_without_inline_keeps_every_finding_in_the_body():
    review = build_review(REPORT, DIFF, inline=False)
    assert review["comments"] == []
    assert "### Findings\n" in review["body"]
    assert "lock is released" in review["body"]


def test_review_post_cli_prints_the_payload(tmp_path):
    (tmp_path / "REVIEW_OUTPUT.md").write_text(REPORT)
    (tmp_path / "pr.diff").write_text(DIFF)
    result = CliRunner().invoke(
        app,
        [
            "review-post",
            "--report",
            str(tmp_path / "REVIEW_OUTPUT.md"),
            "--diff",
            str(tmp_path / "pr.diff"),
            "--event",
            "REQUEST_CHANGES",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["event"] == "REQUEST_CHANGES"
    assert len(payload["comments"]) == 1
