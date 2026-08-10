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
- drop empty qualifiers ("actual", "actually"),
- swap stiff phrasings for their one-word equivalent ("prior to" -> "before").

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
    r"(?:It(?:'?s| is) worth noting that|It(?:'?s| is) important to note that"
    r"|It(?:'?s| is) worth mentioning that|It(?:'?s| is) important to remember that"
    r"|I noticed that|I wanted to point out that"
    r"|I want to (?:point out|note|mention|flag) that|Please note that"
    r"|Just to (?:note|mention)|Worth noting,?|Note that"
    r"|Actually|Personally|Honestly|Frankly|Quite frankly|To be honest"
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
# Sentence-initial "Actually," is handled by the opener list; these cover the
# mid-sentence and trailing uses. The adjective is only dropped after a
# determiner that doesn't inflect, so "an actual bug" is left to the prompt.
_ACTUALLY_TRAIL_RE = re.compile(
    r"(?<=\w)[ \t]*,?[ \t]*\bactually\b(?=[ \t]*(?:[.,;:!?)\]]|$|\n))", re.IGNORECASE
)
_ACTUALLY_MID_RE = re.compile(r"(?<=\w)[ \t]+actually\b", re.IGNORECASE)
# "... works. Actually it does." — mid-line sentence starts, which the opener
# list (anchored to the start of a line) never sees.
_ACTUALLY_SENTENCE_RE = re.compile(r"([.!?][ \t]+)actually\b[ \t,]*(\w)", re.IGNORECASE)
# The word after "actual" must be its noun: a verb, conjunction, or preposition
# there means "the actual" was the noun ("compare the actual to the expected").
_ACTUAL_ADJ_RE = re.compile(
    r"\b(the|this|that|these|those|its|their|our|your|my|no|each|any|every|some|all)"
    r"[ \t]+actual[ \t]+"
    r"(?!(?:is|was|are|were|be|been|and|or|to|vs\.?|versus|of|in|on|at|for|with"
    r"|from|than|but|so|because)\b)(?=\w)",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"(```[\s\S]*?```)")
_INLINE_RE = re.compile(r"(`[^`\n]*`)")

# Stiff phrasings with one short equivalent that reads the same in every
# sentence. Anything whose replacement depends on the surrounding clause ("a
# number of", "in terms of") stays prompt-side, where a model can judge it.
_PHRASINGS = [
    (r"\butilize\b", "use"),
    (r"\butilizes\b", "uses"),
    (r"\butilizing\b", "using"),
    (r"\bleverage\b", "use"),
    (r"\bleverages\b", "uses"),
    (r"\bleveraging\b", "using"),
    (r"\bin order to\b", "to"),
    (r"\bcould potentially\b", "could"),
    (r"\bmay potentially\b", "may"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bin the event that\b", "if"),
    (r"\bprior to\b", "before"),
    (r"\bsubsequent to\b", "after"),
    (r"\bat this point in time\b", "now"),
    (r"\bwith regard(?:s)? to\b", "about"),
    (r"\b(?:is|are) able to\b", "can"),
    (r"\b(?:was|were) able to\b", "could"),
    (r"\bhas the ability to\b", "can"),
    (r"\bhave the ability to\b", "can"),
]
_PHRASING_RES = [(re.compile(p, re.IGNORECASE), r) for p, r in _PHRASINGS]


def _match_case(matched: str, replacement: str) -> str:
    """Capitalize `replacement` iff `matched` was, so line-initial hits keep their capital."""
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _scrub_prose(s: str) -> str:
    # Em / en dashes — the single strongest tell. A dash between two numbers is a
    # range ("35–50 min"), so it collapses to a plain hyphen; spacing it out would
    # read as a subtraction or a dropped clause.
    s = re.sub(r"(?<=\d)\s*[–—]\s*(?=\d)", "-", s)
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
    # Drop "actually" (trailing first, so its comma goes with it) and "actual".
    s = _ACTUALLY_SENTENCE_RE.sub(lambda m: m.group(1) + m.group(2).upper(), s)
    s = _ACTUALLY_TRAIL_RE.sub("", s)
    s = _ACTUALLY_MID_RE.sub("", s)
    s = _ACTUAL_ADJ_RE.sub(lambda m: m.group(1) + " ", s)
    # Safe lexicon and phrasing replacements (leverage -> use, prior to -> before).
    for pattern, replacement in _PHRASING_RES:
        s = pattern.sub(lambda m, r=replacement: _match_case(m.group(0), r), s)
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
