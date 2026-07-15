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
- drop filler/ranking praise leads ("Great catch, ...", "Nice find. ..."),
- tighten a few verbose phrasings.

Code is never touched: fenced ```blocks``` and `inline code` pass through
untouched. Non-strings pass through unchanged.
"""

from __future__ import annotations

import re

# Sentence-initial filler openers, stripped at the start of the text or a line.
# Two families: chatbot "note that" scaffolding, and editorializing verdict
# openers ("Personally", "Honestly", ...) that prime a blunt/dismissive read of
# whatever follows. Both are safe to drop with no loss of meaning.
_OPENERS = (
    r"(?:It'?s worth noting that|It'?s important to note that"
    r"|It'?s worth mentioning that|It'?s important to remember that"
    r"|I noticed that|I wanted to point out that"
    r"|I want to (?:point out|note|mention|flag) that|Please note that"
    r"|Just to (?:note|mention)|Worth noting,?|Note that"
    r"|Personally|Honestly|Frankly|Quite frankly|To be honest"
    r"|In my (?:honest )?opinion|IMO|IMHO|If you ask me"
    r"|At the end of the day|Generally speaking|Now,? more than ever"
    r"|Furthermore|Moreover|Additionally|Consequently|Nevertheless|Indeed)"
)

# Trailing chatbot scaffolding that adds nothing to a comment.
_SCAFFOLD = (
    r"(?:Let me know if[^\n]*|Hope (?:this|that) helps[^\n]*"
    r"|I hope (?:this|that) helps[^\n]*|Feel free to[^\n]*"
    r"|Happy to help[^\n]*|Let me know your thoughts[^\n]*)"
)

# Thanking bots for review or comments. Stripped at the start of the text or a line.
_THANK_BOT = (
    r"(?:Thanks|Thank you)(?:\s+(?:for the review|for the feedback"
    r"|for pointing this out|for the comment))?"
    r"\s*,?\s*@?[-\w]*(?:bots?|actions?|cov|guard|lgtm|sonar|copilot|renovate)\b"
)

# Sentence-initial apologies. Stripped at the start of the text or a line.
_APOLOGIES = (
    r"(?:My apologies|Sorry (?:about that|for the oversight|for the confusion)"
    r"|Apologies for the (?:oversight|confusion|mistake))"
)

# Filler / ranking praise that leads a comment ("Great catch", "Nice find") — a
# reliable AI tell. Kept to fixed adjective+noun phrases; free-form ranking ("the
# sharpest catch in the review") and "good catch" at a bot stay prompt-side, since
# generalizing them would strip legitimate prose ("the most important issue here").
_PRAISE = (
    r"(?:(?:Great|Nice|Good|Excellent|Fantastic|Awesome|Wonderful|Solid"
    r"|Strong|Fair)[ \t]+(?:catch|find|point|call|callout|call-out"
    r"|observation|spot|work)|Well spotted|Good eye|Nice one|Spot on)"
)

_OPENER_RE = re.compile(r"(^|\n)[ \t]*" + _OPENERS + r"[ \t,]+(\w)", re.IGNORECASE)
_SCAFFOLD_RE = re.compile(r"(?:^|\n)\s*" + _SCAFFOLD + r"\s*$", re.IGNORECASE)
# A praise phrase that IS the whole line (optionally punctuated) — drop it.
_PRAISE_LINE_RE = re.compile(
    r"(^|\n)[ \t]*" + _PRAISE + r"[ \t]*[.!]*[ \t]*(?=\n|$)", re.IGNORECASE
)
# A praise phrase leading into real content, separated by punctuation
# ("Great catch, this races" / "Nice find. This leaks") — strip it, recapitalize.
# Punctuation is required so "Good point about X" (a real sentence) is left alone.
_PRAISE_LEAD_RE = re.compile(r"(^|\n)[ \t]*" + _PRAISE + r"[ \t]*[,.:!]+[ \t]*(\w)", re.IGNORECASE)
_THANK_BOT_LEAD_RE = re.compile(r"(^|\n)[ \t]*" + _THANK_BOT + r"[ \t,!.?]*(\w)", re.IGNORECASE)
_THANK_BOT_LINE_RE = re.compile(r"(^|\n)[ \t]*" + _THANK_BOT + r"[ \t,!.?]*(?=\n|$)", re.IGNORECASE)
_APOLOGY_LEAD_RE = re.compile(r"(^|\n)[ \t]*" + _APOLOGIES + r"[ \t,!.?]*(\w)", re.IGNORECASE)
_APOLOGY_LINE_RE = re.compile(r"(^|\n)[ \t]*" + _APOLOGIES + r"[ \t,!.?]*(?=\n|$)", re.IGNORECASE)
_FENCE_RE = re.compile(r"(```[\s\S]*?```)")
_INLINE_RE = re.compile(r"(`[^`\n]*`)")


def _scrub_prose(s: str) -> str:
    # Em / en dashes — the single strongest tell.
    s = re.sub(r"\s*—\s*", ", ", s)
    s = re.sub(r"\s*–\s*", " - ", s)
    # Drop overused AI emojis.
    s = re.sub(r"[🚀✨🔑💡🎯😊🙏]", "", s)
    # Drop trailing scaffolding sentences/lines.
    s = _SCAFFOLD_RE.sub("", s)
    # Drop standalone praise lines, then strip praise that leads into content.
    s = _PRAISE_LINE_RE.sub(lambda m: m.group(1), s)
    s = _PRAISE_LEAD_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    # Drop standalone bot-thanks, then strip bot-thanks that leads into content.
    s = _THANK_BOT_LINE_RE.sub(lambda m: m.group(1), s)
    s = _THANK_BOT_LEAD_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    # Drop standalone apologies, then strip apologies that lead into content.
    s = _APOLOGY_LINE_RE.sub(lambda m: m.group(1), s)
    s = _APOLOGY_LEAD_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    # Strip filler openers at the start of the text or a line; recapitalize.
    s = _OPENER_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    # Safe lexicon replacements: leverage/utilize -> use.
    s = re.sub(r"\butilize\b", "use", s, flags=re.IGNORECASE)
    s = re.sub(r"\butilizes\b", "uses", s, flags=re.IGNORECASE)
    s = re.sub(r"\butilizing\b", "using", s, flags=re.IGNORECASE)
    s = re.sub(r"\bleverage\b", "use", s, flags=re.IGNORECASE)
    s = re.sub(r"\bleverages\b", "uses", s, flags=re.IGNORECASE)
    s = re.sub(r"\bleveraging\b", "using", s, flags=re.IGNORECASE)
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
