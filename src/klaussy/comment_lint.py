"""Deterministic verbose-comment detector — the block-only precommit backstop.

Format, lint, and ruff's ERA rule judge commented-out *code* but never comment
*prose*, so a narration block that restates the code sails through; this module
flags over-long comments for the author to trim, and like ERA it is block-only
and never edits source — which sentence of a comment is the one worth keeping is
a judgment call, so the author (or the agent) makes it, not a regex. Three
heuristics trip a finding: a run of `COMMENT_RUN_MAX`+ consecutive full-line
prose comments, a single comment over `COMMENT_WORD_MAX` words, or one logical
comment running past `COMMENT_SENTENCE_MAX` sentences.
Exempt: Python docstrings, tooling directives (`# noqa`, `// eslint-disable`),
bare URLs, and the leading license/shebang/banner block. Python is read via stdlib
`tokenize` so a `#` inside a string isn't mistaken for a comment (line-scan
fallback on syntax error); C-style languages use a line scanner that ignores
inline `//` to dodge the `http://` trap.
"""

from __future__ import annotations

import io
import re
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path

# A run of this many consecutive full-line prose comments is "a block".
COMMENT_RUN_MAX = 4
# A single comment longer than this (in words) is "too long" on its own.
COMMENT_WORD_MAX = 30
# Sentences a comment may spend before it reads as narration. Two leaves room
# for the claim-plus-why shape a real comment needs; a third usually restates
# the code.
COMMENT_SENTENCE_MAX = 2

# Extensions whose line comments start with `#`. Python is read via tokenize;
# the rest fall back to the line scanner (full-line comments only).
_PY_EXT = {".py", ".pyi"}
_HASH_EXT = _PY_EXT | {".sh", ".bash", ".zsh", ".rb", ".pl", ".r"}
# Extensions with C-style `//` line comments and `/* */` block comments.
_SLASH_EXT = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".php",
}

# Tooling directives and bare URLs — not prose, never flagged. Matched against
# the comment text after its marker and surrounding whitespace are stripped.
_DIRECTIVE_RE = re.compile(
    r"^(?:"
    r"!"  # shebang remnant (#!...)
    r"|noqa\b|type:\s|pyright:|mypy:|ruff:|pylint:|flake8:|nosec\b|nocov\b"
    r"|pragma\b|fmt:\s|isort:|coding[:=]|-\*-"
    r"|eslint|@ts-|prettier|c8\b|istanbul|@flow\b|jshint|jslint|global\s"
    r"|https?://\S+$"
    r")",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

# A sentence ends at terminal punctuation followed by whitespace and a capital.
# Requiring the capital is what keeps `hooks.py`, `0.16.0`, `klaussy.toolkit`,
# and a trailing URL from splitting a sentence — their dots are mid-token.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Words whose trailing dot is an abbreviation, not a sentence end — without
# these, `e.g. Claude` reads as a break. Compared lowercased, terminators stripped.
_ABBREVIATIONS = frozenset({"e.g", "i.e", "etc", "vs", "cf", "al", "approx", "resp", "viz"})


@dataclass(frozen=True)
class Finding:
    """One verbose comment the guard should block on."""

    path: str
    start: int  # 1-based first line
    end: int  # 1-based last line (== start for a single-line finding)
    detail: str  # human reason, e.g. "6 lines" or "38 words"

    def render(self) -> str:
        loc = f"{self.path}:{self.start}"
        if self.end != self.start:
            loc += f"-{self.end}"
        return f"{loc}: verbose comment ({self.detail}) — strip to the bare minimum and re-commit"


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _sentence_count(text: str) -> int:
    """Sentences in `text`, deliberately erring low.

    A miscount here blocks a commit, so every ambiguous break is resolved as
    "not a break" — under-counting lets a wordy comment through, over-counting
    rejects a comment the author can't see the fault in.
    """
    text = text.strip()
    if not text:
        return 0
    count = 1
    for match in _SENTENCE_BREAK.finditer(text):
        preceding = text[: match.start()].split()
        if preceding and preceding[-1].rstrip(".!?\"')").lower() in _ABBREVIATIONS:
            continue
        count += 1
    return count


def _is_directive(text: str) -> bool:
    return bool(_DIRECTIVE_RE.match(text))


# A comment record: (lineno, full_line, text). `full_line` is True when nothing
# but whitespace precedes the comment marker on its line.
_Record = tuple[int, bool, str]


def _python_comments(text: str) -> list[_Record] | None:
    """Comment records via tokenize (string-safe). None signals a parse error."""
    out: list[_Record] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                full = tok.line[:col].strip() == ""
                out.append((row, full, tok.string.lstrip("#").strip()))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return None
    return out


def _hash_line_comments(text: str) -> list[_Record]:
    """Full-line `#` comments only — inline `#` is skipped to avoid strings."""
    out: list[_Record] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            out.append((i, True, stripped[1:].strip()))
    return out


def _slash_comments(text: str) -> list[_Record]:
    """Full-line `//` comments and `/* */` blocks; `/**` JSDoc is exempt.

    Inline `//` is intentionally ignored — it's where `http://` lives and it
    rarely carries the narration blocks this check targets.
    """
    out: list[_Record] = []
    in_block = False
    jsdoc = False
    for i, line in enumerate(text.splitlines(), 1):
        if in_block:
            seg = line.split("*/", 1)[0] if "*/" in line else line
            if not jsdoc:
                out.append((i, True, seg.strip().lstrip("*").strip()))
            if "*/" in line:
                in_block = False
            continue
        stripped = line.strip()
        if stripped.startswith("//"):
            out.append((i, True, stripped[2:].strip()))
        elif "/*" in line:
            before, after = line.split("/*", 1)
            jsdoc = after.startswith("*")
            full = before.strip() == ""
            if "*/" in after:  # block opens and closes on one line
                if not jsdoc:
                    inner = after.split("*/", 1)[0].strip().lstrip("*").strip()
                    out.append((i, full, inner))
            else:
                in_block = True
                if not jsdoc:
                    out.append((i, full, after.strip().lstrip("*").strip()))
    return out


def _first_code_line(text: str, comment_lines: set[int]) -> int:
    """1-based line of the first line that is neither blank nor a comment."""
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip() and i not in comment_lines:
            return i
    return len(text.splitlines()) + 1  # whole file is comments/blanks


def _header_lines(prose: list[tuple[int, str]], first_code: int) -> set[int]:
    """The leading license/shebang/banner block — the contiguous comment run
    that sits entirely above the first line of code."""
    header: set[int] = set()
    prev: int | None = None
    for ln, _ in prose:
        if ln >= first_code or (prev is not None and ln != prev + 1):
            break
        header.add(ln)
        prev = ln
    return header


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(path: str) -> set[int] | None:
    """Working-tree line numbers added/changed vs HEAD for `path`.

    Returns a set of 1-based line numbers that differ from HEAD, for scoping
    findings to the diff in flight. Returns None — meaning "treat the whole
    file as changed" — when the diff can't be trusted to under-report: git is
    unavailable, the file is untracked/new (no HEAD version), or git errors.
    An empty set means the file is tracked but has no changes vs HEAD.

    Line numbers are read from `git diff HEAD` hunk headers, which index the
    working-tree side — the same text `analyze()` reads from disk.
    """
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--unified=0", "--no-color", "--", path],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if diff.returncode != 0:
        return None
    if not diff.stdout.strip():
        # No diff: either an unchanged tracked file (→ empty set, nothing to
        # flag) or an untracked file with no HEAD side (→ whole file is new).
        try:
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", path],
                capture_output=True,
                text=True,
            )
        except OSError:
            return None
        return set() if tracked.returncode == 0 else None

    out: set[int] = set()
    for line in diff.stdout.splitlines():
        m = _HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group(1))
        count = 1 if m.group(2) is None else int(m.group(2))
        out.update(range(start, start + count))
    return out


def _findings(path: str, text: str, records: list[_Record]) -> list[Finding]:
    findings: list[Finding] = []
    prose = [(ln, txt) for ln, full, txt in records if full and txt and not _is_directive(txt)]
    first_code = _first_code_line(text, {ln for ln, _, _ in records})
    header = _header_lines(prose, first_code)

    # Consecutive full-line prose comments form one logical comment, so the run —
    # not the line — is what heuristics 1 and 3 judge.
    runs: list[list[tuple[int, str]]] = []
    run: list[tuple[int, str]] = []
    for ln, txt in prose:
        if ln in header:
            if run:
                runs.append(run)
            run = []
            continue
        if run and ln != run[-1][0] + 1:
            runs.append(run)
            run = []
        run.append((ln, txt))
    if run:
        runs.append(run)

    flagged: set[int] = set()
    for block in runs:
        # Heuristic 1: too many consecutive lines of prose.
        if len(block) >= COMMENT_RUN_MAX:
            findings.append(Finding(path, block[0][0], block[-1][0], f"{len(block)} lines"))
            flagged.update(ln for ln, _ in block)
            continue
        # Heuristic 3: too many sentences, however few lines it spans.
        sentences = _sentence_count(" ".join(txt for _, txt in block))
        if sentences > COMMENT_SENTENCE_MAX:
            findings.append(Finding(path, block[0][0], block[-1][0], f"{sentences} sentences"))
            flagged.update(ln for ln, _ in block)

    # Heuristic 2: a single over-long comment (full-line or inline), unless it's
    # already inside a flagged block or part of the file header.
    for ln, _, txt in records:
        if ln in header or ln in flagged or not txt or _is_directive(txt):
            continue
        words = _word_count(txt)
        if words > COMMENT_WORD_MAX:
            findings.append(Finding(path, ln, ln, f"{words} words"))

    findings.sort(key=lambda f: (f.start, f.end))
    return findings


def _overlaps(finding: Finding, scope: set[int]) -> bool:
    return any(ln in scope for ln in range(finding.start, finding.end + 1))


def analyze(path: str, text: str, scope: set[int] | None = None) -> list[Finding]:
    """Return verbose-comment findings for one file's text. Empty when clean.

    When `scope` is a set of line numbers, only findings that overlap those
    lines are returned — used to limit the check to the diff in flight so
    pre-existing comments elsewhere in the file don't block a commit. `None`
    (the default) reports across the whole file.
    """
    ext = Path(path).suffix.lower()
    if ext in _PY_EXT:
        records = _python_comments(text)
        if records is None:
            records = _hash_line_comments(text)
    elif ext in _HASH_EXT:
        records = _hash_line_comments(text)
    elif ext in _SLASH_EXT:
        records = _slash_comments(text)
    else:
        return []
    findings = _findings(path, text, records)
    if scope is not None:
        findings = [f for f in findings if _overlaps(f, scope)]
    return findings
