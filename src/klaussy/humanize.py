"""Deterministic, code-preserving humanizer for agent prose output.

This is the canonical Python port of klaussy-desktop's
`main/util/humanize-comment.js` — kept here so klaussy owns the scrubbing logic
and consumers (the desktop app, CI, hooks) don't each maintain a divergent copy.
It is the deterministic backstop to the prompt-side `{{HUMANIZE}}` guidance: the
prompt asks the agent to write human prose; this guarantees it regardless of how
well the model complied.

Conservative by design — high-confidence, meaning-preserving edits only:
- normalize em/en dashes in prose,
- strip sentence-initial filler openers (and re-capitalize),
- drop trailing chatbot scaffolding lines,
- tighten a few verbose phrasings.

Code is never touched: fenced ```blocks``` and `inline code` pass through
untouched. Non-strings pass through unchanged.
"""

from __future__ import annotations

import re

# Sentence-initial filler openers, stripped at the start of the text or a line.
_OPENERS = (
    r"(?:It'?s worth noting that|It'?s important to note that"
    r"|It'?s worth mentioning that|I noticed that|I wanted to point out that"
    r"|I want to (?:point out|note|mention|flag) that|Please note that"
    r"|Just to (?:note|mention)|Worth noting,?|Note that)"
)

# Trailing chatbot scaffolding that adds nothing to a comment.
_SCAFFOLD = (
    r"(?:Let me know if[^\n]*|Hope (?:this|that) helps[^\n]*"
    r"|I hope (?:this|that) helps[^\n]*|Feel free to[^\n]*"
    r"|Happy to help[^\n]*|Let me know your thoughts[^\n]*)"
)

_OPENER_RE = re.compile(r"(^|\n)[ \t]*" + _OPENERS + r"[ \t,]+(\w)", re.IGNORECASE)
_SCAFFOLD_RE = re.compile(r"(?:^|\n)\s*" + _SCAFFOLD + r"\s*$", re.IGNORECASE)
_FENCE_RE = re.compile(r"(```[\s\S]*?```)")
_INLINE_RE = re.compile(r"(`[^`\n]*`)")


def _scrub_prose(s: str) -> str:
    # Em / en dashes — the single strongest tell.
    s = re.sub(r"\s*—\s*", ", ", s)
    s = re.sub(r"\s*–\s*", " - ", s)
    # Drop trailing scaffolding sentences/lines.
    s = _SCAFFOLD_RE.sub("", s)
    # Strip filler openers at the start of the text or a line; recapitalize.
    s = _OPENER_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    # A few safe, unambiguous tightenings.
    s = re.sub(r"\bin order to\b", "to", s, flags=re.IGNORECASE)
    s = re.sub(r"\bcould potentially\b", "could", s, flags=re.IGNORECASE)
    s = re.sub(r"\bmay potentially\b", "may", s, flags=re.IGNORECASE)
    # Tidy whitespace introduced by the removals.
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[ \t]+(\n)", r"\1", s)
    return s


def humanize(text: str) -> str:
    """Return the humanized string; pass non-strings/empty through unchanged."""
    if not isinstance(text, str) or not text:
        return text
    # Preserve fenced and inline code: only the even segments are prose.
    fence_parts = _FENCE_RE.split(text)
    for i in range(0, len(fence_parts), 2):
        inline = _INLINE_RE.split(fence_parts[i])
        for j in range(0, len(inline), 2):
            inline[j] = _scrub_prose(inline[j])
        fence_parts[i] = "".join(inline)
    return re.sub(r"\n{3,}", "\n\n", "".join(fence_parts)).strip()
