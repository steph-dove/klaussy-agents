"""Turn the review skill's REVIEW_OUTPUT.md into a GitHub pull request review."""

from __future__ import annotations

import codecs
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

_FINDING = re.compile(r"^\*\*(?!Verdict)(?P<meta>[^*\n]*·[^*\n]*)\*\*\s*$", re.MULTILINE)
# A path needs an extension or a slash, or is a known extensionless file, so `localhost:8080`
# and `10:30` aren't read as locations.
_BARE_NAMES = "Makefile|Dockerfile|Rakefile|Gemfile|Procfile|Justfile|Vagrantfile"
_PATH = (
    r"(?:[\w./-]+\.\w+|[\w./-]*/[\w.-]+"
    rf"|(?:[\w./-]*/)?(?:{_BARE_NAMES}|\.\w[\w.-]*))"
)
_LOCATION = re.compile(rf"({_PATH}):(\d+)(?:\s*[-–]\s*(\d+))?")
_BARE_PATH = re.compile(_PATH)
_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_BODY_END = re.compile(r"^(\*\*Verdict:|#{1,3} |---\s*$)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_VERDICT = re.compile(r"^\*\*Verdict:", re.MULTILINE)
_APPROVED = re.compile(r"^\*\*Verdict:[\s*_]*Approve\b", re.MULTILINE)


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
        """The `file:line[-line]` in the location; the body's only when the location names no
        file, or names the same file."""
        m = _LOCATION.search(self.location)
        if not m:
            named = _BARE_PATH.search(self.location)
            for candidate in _LOCATION.finditer(self.body):
                if not named or candidate.group(1).removeprefix("./") == named.group(
                    0
                ).removeprefix("./"):
                    m = candidate
                    break
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
        body = _finding_body(report[m.end() : end])
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


def _finding_body(text: str) -> str:
    """Text up to the next section break; a `#` or `---` inside a code fence isn't one."""
    kept, fenced = [], False
    for line in text.splitlines(keepends=True):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and _BODY_END.match(line):
            break
        kept.append(line)
    return "".join(kept)


def _diff_path(header: str) -> str | None:
    """The path in a `+++ ` header, without git's trailing tab or C-style quoting."""
    name = header[4:].split("\t", 1)[0]
    if len(name) > 1 and name.startswith('"') and name.endswith('"'):
        name = codecs.escape_decode(name[1:-1].encode())[0].decode("utf-8", "replace")
    return None if name == "/dev/null" else name.removeprefix("b/")


def commentable_lines(diff: str) -> dict[str, set[int]]:
    """Head-side line numbers a review comment can attach to, per file in a unified diff."""
    lines: dict[str, set[int]] = {}
    path, line, old_left, new_left = None, 0, 0, 0
    for row in diff.split("\n"):
        if old_left > 0 or new_left > 0:
            if row.startswith("\\"):
                continue
            if row.startswith("-"):
                old_left -= 1
                continue
            if path is not None:
                lines.setdefault(path, set()).add(line)
            line += 1
            new_left -= 1
            if not row.startswith("+"):
                old_left -= 1
            continue
        hunk = _HUNK.match(row)
        if hunk:
            old_left = int(hunk.group(1) or 1)
            line = int(hunk.group(2))
            new_left = int(hunk.group(3) or 1)
        elif row.startswith("+++ "):
            path = _diff_path(row)
    return lines


def summary(report: str) -> str:
    """The verdict section, else the whole report when no findings parse, else nothing."""
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
    commit: str | None = None,
) -> dict:
    """A PR review payload; findings outside the diff go in the body, which GitHub requires."""
    report = redact(report, secrets)
    findings = parse_findings(report)
    approved = bool(_APPROVED.search(report))
    # The event follows the reviewer: no blocking a clean approval, no approving what it blocked.
    if (event == "REQUEST_CHANGES" and not findings and approved) or (
        event == "APPROVE" and not approved
    ):
        event = "COMMENT"
    commentable = commentable_lines(diff) if inline else {}
    comments, unplaced = [], []
    for f in findings:
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
    review = {"event": event, "body": body, "comments": comments}
    if commit:
        review["commit_id"] = commit
    return review
