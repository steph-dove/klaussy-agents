import json

from typer.testing import CliRunner

from klaussy.cli import app
from klaussy.review_post import (
    FOOTER,
    MARKER,
    WATERMARK,
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
            "body": parse_findings(REPORT)[0].comment,
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


def test_build_review_redacts_secrets_from_body_and_comments():
    leaked = "sk-ant-api03-" + "x" * 30
    report = REPORT.replace(
        "Hold it until the write returns.", f"Hold it. Env: {leaked} hunter2hunter2"
    ).replace("Consider splitting the module.", f"Key {leaked}")
    review = build_review(report, DIFF, secrets=["hunter2hunter2"])
    posted = review["body"] + "".join(c["body"] for c in review["comments"])
    assert leaked not in posted and "hunter2hunter2" not in posted
    assert "[redacted]" in posted


def test_review_post_cli_redacts_credentials_from_the_environment(tmp_path, monkeypatch):
    leaked = "-".join(["plain", "oauth", "token", "value"])
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", leaked)
    (tmp_path / "REVIEW_OUTPUT.md").write_text(REPORT.replace("splitting", leaked))
    (tmp_path / "pr.diff").write_text(DIFF)
    args = ["review-post", "--report", str(tmp_path / "REVIEW_OUTPUT.md")]
    result = CliRunner().invoke(app, [*args, "--diff", str(tmp_path / "pr.diff")])
    assert result.exit_code == 0, result.output
    assert leaked not in result.output


def test_a_heading_or_rule_inside_a_code_fence_stays_in_the_finding():
    report = (
        "**High · Correctness · `app.py:3`**\n\nThe default is wrong.\n\n"
        "```yaml\n# keep this comment\n---\nretries: 3\n```\n\n"
        "**Verdict:** Request Changes\n"
    )
    body = parse_findings(report)[0].body
    assert body.endswith("retries: 3\n```")
    assert "# keep this comment" in body and "Verdict" not in body


def test_request_changes_falls_back_to_comment_only_for_an_approved_clean_report():
    clean = "**Verdict:** Approve · reviewed at `abc1234`\n"
    assert build_review(clean, DIFF, event="REQUEST_CHANGES")["event"] == "COMMENT"
    assert build_review(REPORT, DIFF, event="REQUEST_CHANGES")["event"] == "REQUEST_CHANGES"
    unparsed = "Found a race in pool.py.\n\n**Verdict:** Request Changes\n"
    assert build_review(unparsed, DIFF, event="REQUEST_CHANGES")["event"] == "REQUEST_CHANGES"


def test_commentable_lines_only_reads_headers_outside_hunks():
    diff = (
        "diff --git a/notes.md b/notes.md\n"
        "--- a/notes.md\n"
        "+++ b/notes.md\n"
        "@@ -1,1 +1,3 @@\n"
        " title\n"
        "+-- not a header\n"
        "+++ also not a header\n"
        'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'
        '--- "a/caf\\303\\251.py"\n'
        '+++ "b/caf\\303\\251.py"\n'
        "@@ -0,0 +1 @@\n"
        "+x = 1\n"
        "diff --git a/my file.py b/my file.py\n"
        "--- a/my file.py\t\n"
        "+++ b/my file.py\t\n"
        "@@ -0,0 +1 @@\n"
        "+y = 2\n"
    )
    assert commentable_lines(diff) == {
        "notes.md": {1, 2, 3},
        "café.py": {1},
        "my file.py": {1},
    }


def test_the_review_is_pinned_to_the_commit_the_diff_was_taken_at():
    assert build_review(REPORT, DIFF, commit="abc1234")["commit_id"] == "abc1234"
    assert "commit_id" not in build_review(REPORT, DIFF)


def test_a_bolded_approve_verdict_still_counts_as_approval():
    clean = "**Verdict:** **Approve** · reviewed at `abc1234`\n"
    assert build_review(clean, DIFF, event="REQUEST_CHANGES")["event"] == "COMMENT"


def test_a_one_span_bold_verdict_is_neither_a_finding_nor_a_block():
    report = "**Verdict: Approve · reviewed at abc1234**\n"
    assert parse_findings(report) == []
    assert build_review(report, DIFF, event="REQUEST_CHANGES")["event"] == "COMMENT"


def test_an_extensionless_location_is_placed_on_its_own_file():
    report = "**Medium · Build · `Makefile:2`**\n\nSame bug as `src/pool.py:11`.\n"
    assert parse_findings(report)[0].place() == ("Makefile", 2, 2)


def test_review_post_cli_survives_a_non_utf8_diff(tmp_path):
    (tmp_path / "REVIEW_OUTPUT.md").write_text(REPORT)
    (tmp_path / "pr.diff").write_bytes(DIFF.encode() + b"+caf\xe9 = 1\n")
    args = ["review-post", "--report", str(tmp_path / "REVIEW_OUTPUT.md")]
    result = CliRunner().invoke(app, [*args, "--diff", str(tmp_path / "pr.diff")])
    assert result.exit_code == 0, result.output


def test_host_ports_and_times_are_not_locations():
    report = "**Medium · Config · the service config**\n\nIt listens on localhost:8080 at 10:30.\n"
    assert parse_findings(report)[0].place() is None


def test_a_location_naming_a_file_only_borrows_a_line_for_that_file():
    other = "**Medium · Bug · `src/a.py`**\n\nSame as src/b.py:12.\n"
    same = "**Medium · Bug · `src/a.py`**\n\nSee src/a.py:7 and src/b.py:12.\n"
    assert parse_findings(other)[0].place() is None
    assert parse_findings(same)[0].place() == ("src/a.py", 7, 7)


def test_approve_is_only_posted_when_the_reviewer_approved():
    assert build_review(REPORT, DIFF, event="APPROVE")["event"] == "COMMENT"
    clean = "**Verdict:** Approve · reviewed at `abc1234`\n"
    assert build_review(clean, DIFF, event="APPROVE")["event"] == "APPROVE"


FIX_FINDING = """**High · Correctness · `src/pool.py:11`**

The lock is released before the write, e.g. on the put path. Another thread can then
append in between. That corrupts the pool under load.

Suggested change:
```python
with self.lock:
    self.conns.append(conn)
```
"""


def test_a_comment_reads_like_klaussy_desktop_posts_it():
    comment = parse_findings(FIX_FINDING)[0].comment
    lead, details = comment.split("\n\n<details>", 1)
    assert lead.startswith(
        "The lock is released before the write, e.g. on the put path.\n\n```python"
    )
    assert "High" not in lead and "Correctness" not in lead
    assert details.startswith("\n<summary>Explanation</summary>")
    assert "That corrupts the pool under load." in details
    assert details.rstrip().endswith(f"<sub>{WATERMARK}</sub>\n\n</details>")


def test_every_comment_carries_the_watermark_in_its_explanation():
    short = "**Low · Docs · `README.md:4`**\n\nThe README still says the pool is unbounded.\n"
    comment = parse_findings(short)[0].comment
    assert comment.startswith("The README still says the pool is unbounded.\n\n<details>")
    assert f"<sub>{WATERMARK}</sub>" in comment


def test_comments_are_humanized_but_code_is_left_alone():
    report = (
        "**Medium · Style · `app.py:3`**\n\n"
        "Great catch: the retry loop runs forever \u2014 it never backs off.\n\n"
        "Suggested change:\n```python\nx = a \u2014 b\n```\n"
    )
    comment = parse_findings(report)[0].comment
    lead = comment.split("<details>")[0]
    assert "Great catch" not in lead and "\u2014 it never" not in lead
    assert "x = a \u2014 b" in comment


def test_findings_outside_the_diff_keep_their_location_but_not_severity():
    body = build_review(REPORT, DIFF)["body"]
    assert "`README.md:40`\n\nThe README still says" in body
    assert "**Medium · Docs" not in body
