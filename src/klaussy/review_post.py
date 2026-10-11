"""Turn the review skill's REVIEW_OUTPUT.md into a GitHub pull request review."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from klaussy.secret_scan import redact

MARKER = "<!-- klaussy-review -->"
CREDENTIAL_ENV = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)
FOOTER = "Reviewed by [klaussy](https://klaussy.com)."

_FINDING = re.compile(r"^\*\*(?P<meta>[^*\n]*·[^*\n]*)\*\*\s*$", re.MULTILINE)
_LOCATION = re.compile(r"([\w./-]+\.\w+|[\w./-]*/[\w.-]+):(\d+)(?:\s*[-–]\s*(\d+))?")
_DIFF_FILE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_VERDICT = re.compile(r"^\*\*Verdict:", re.MULTILINE)


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    location: str
    body: str

    @property
    def text(self) -> str:
        meta = " · ".join(p for p in (self.severity, self.category, f"`{self.location}`") if p)
        return f"**{meta}**\n\n{self.body}"

    @property
    def inline_text(self) -> str:
        meta = " · ".join(p for p in (self.severity, self.category) if p)
        return f"**{meta}**\n\n{self.body}"

    def place(self) -> tuple[str, int, int] | None:
        """The first `file:line[-line]` in the location, else in the body."""
        m = _LOCATION.search(self.location) or _LOCATION.search(self.body)
        if not m:
            return None
        start = int(m.group(2))
        return m.group(1).removeprefix("./"), start, max(start, int(m.group(3) or start))


def parse_findings(report: str) -> list[Finding]:
    """Split a report into findings at the skill's `**Sev · Cat · loc**` lines."""
    marks = list(_FINDING.finditer(report))
    findings = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(report)
        body = report[m.end() : end]
        body = re.split(r"^\*\*Verdict:|^#{1,3} |^---\s*$", body, maxsplit=1, flags=re.M)[0]
        parts = [p.strip(" `") for p in m.group("meta").split("·")]
        findings.append(
            Finding(
                severity=parts[0],
                category=parts[1] if len(parts) > 2 else "",
                location=parts[-1],
                body=body.strip(),
            )
        )
    return findings


def commentable_lines(diff: str) -> dict[str, set[int]]:
    """Head-side line numbers a review comment can attach to, per file in a unified diff."""
    lines: dict[str, set[int]] = {}
    path, line = None, 0
    for row in diff.splitlines():
        if row.startswith("+++ "):
            m = _DIFF_FILE.match(row)
            path = None if not m or m.group(1) == "/dev/null" else m.group(1)
            continue
        hunk = _HUNK.match(row)
        if hunk:
            line = int(hunk.group(1))
            continue
        if path is None or row.startswith(("---", "diff ", "index ", "\\")):
            continue
        if row.startswith("-"):
            continue
        if row.startswith(("+", " ")):
            lines.setdefault(path, set()).add(line)
            line += 1
    return lines


def summary(report: str) -> str:
    """The verdict section the skill closes with, or the whole report if it has none."""
    m = _VERDICT.search(report)
    if m:
        return report[m.start() :].strip()
    return "" if parse_findings(report) else report.strip()


def build_review(
    report: str,
    diff: str,
    *,
    event: str = "COMMENT",
    inline: bool = True,
    secrets: Iterable[str] = (),
) -> dict:
    """A PR review payload; findings outside the diff go in the body, which GitHub requires."""
    report = redact(report, secrets)
    commentable = commentable_lines(diff) if inline else {}
    comments, unplaced = [], []
    for f in parse_findings(report):
        where = f.place()
        lines = commentable.get(where[0], set()) if where else set()
        if not where or where[2] not in lines:
            unplaced.append(f)
            continue
        path, start, end = where
        comment = {"path": path, "line": end, "side": "RIGHT", "body": f.inline_text}
        if start < end and all(n in lines for n in range(start, end + 1)):
            comment.update(start_line=start, start_side="RIGHT")
        comments.append(comment)

    parts = [summary(report)]
    if unplaced:
        heading = "Findings" if not comments else "Findings outside the diff"
        parts.append(f"### {heading}\n\n" + "\n\n".join(f.text for f in unplaced))
    parts.append(f"{FOOTER}\n{MARKER}")
    body = "\n\n".join(p for p in parts if p)
    return {"event": event, "body": body, "comments": comments}
