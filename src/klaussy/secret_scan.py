"""Deterministic secret scanner for the pre-commit guard.

Flags high-signal credential patterns on ADDED lines only (scoped via
`changed_lines`), so a commit that introduces a key is blocked while pre-existing
values elsewhere in a touched file are not. Block-only: it reports `file:line`
and the kind of secret; it never edits. Mirrors `comment_lint`'s shape so the
guard runs it the same way (`klaussy secret-scan --diff <paths>`).

The pattern set is deliberately narrow. A secret guard that cries wolf gets
disabled, so the high-confidence provider tokens (which effectively never
false-positive) are separated from a generic `key = "value"` heuristic that is
gated hard on entropy and a placeholder allowlist.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from klaussy.comment_lint import changed_lines

# Provider tokens with a fixed, unmistakable shape — flagged on sight.
_HIGH_CONFIDENCE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[posru]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\bsk_live_[0-9A-Za-z]{24,}\b")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{20,}T3BlbkFJ[A-Za-z0-9]{20,}\b")),
)

# Generic `secret_name = "value"` assignments. Only flagged when the value also
# clears the entropy/placeholder gate below — the name alone is not enough.
_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:api[_-]?key|secret|password|passwd|token|access[_-]?key|client[_-]?secret|
       auth[_-]?token|private[_-]?key)\b
    \s*[:=]\s*
    (?P<q>['"])(?P<val>[^'"]{8,})(?P=q)
    """
)

# Values that look like secrets but obviously aren't — env lookups, template
# holes, and the usual fake stand-ins. Matched against the captured value.
_PLACEHOLDER = re.compile(
    r"""(?ix)
    (^\s*$)
  | (your[_-]?|example|placeholder|change[_-]?me|redacted|dummy|sample|fake|
     xxx|\.\.\.|todo|none|null|<[^>]+>|\$\{?[a-z_]|%[sd]|\{\{|
     os\.environ|process\.env|getenv|env\[)
    """
)


@dataclass
class Finding:
    """A suspected secret at `path:line`."""

    path: str
    line: int
    kind: str

    def render(self) -> str:
        return (
            f"{self.path}:{self.line}: possible secret ({self.kind}) — remove it before committing"
        )


def _shannon_entropy(value: str) -> float:
    """Bits-per-character Shannon entropy of `value`."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_secret(value: str) -> bool:
    """True if a generic-assignment value is plausibly a real credential."""
    if _PLACEHOLDER.search(value):
        return False
    # A real key is long and high-entropy; a config word like "postgres" is not.
    return len(value) >= 12 and _shannon_entropy(value) >= 3.5


def analyze(path: str, text: str, scope: set[int] | None = None) -> list[Finding]:
    """Return suspected-secret findings in `text`, optionally scoped to `scope` lines."""
    findings: list[Finding] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if scope is not None and idx not in scope:
            continue
        for kind, pattern in _HIGH_CONFIDENCE:
            if pattern.search(line):
                findings.append(Finding(path, idx, kind))
                break
        else:
            m = _ASSIGNMENT.search(line)
            if m and _looks_secret(m.group("val")):
                findings.append(Finding(path, idx, "hardcoded credential"))
    return findings


def scan_paths(paths: list[str], *, diff: bool) -> list[Finding]:
    """Scan each path; with `diff`, restrict to lines changed vs HEAD."""
    findings: list[Finding] = []
    for path in paths:
        try:
            text = _read(path)
        except (OSError, UnicodeDecodeError):
            continue
        scope = changed_lines(path) if diff else None
        findings.extend(analyze(path, text, scope))
    return findings


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()
