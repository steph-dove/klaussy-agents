# Copyright 2026 Dovatech LLC. SPDX-License-Identifier: FSL-1.1-MIT
"""Attribution watermark stamped onto every skill file klaussy emits."""

from __future__ import annotations

SKILL_LICENSE = "FSL-1.1-MIT"

WATERMARK = (
    "<!-- Made with klaussy by Dovatech LLC. Creator: Stephanie Dover. "
    f"© 2026 Dovatech LLC. Licensed under {SKILL_LICENSE}: "
    "https://github.com/steph-dove/klaussy-agents/blob/main/LICENSE -->"
)

_FRONTMATTER_END = "\n---\n"


def watermark_skill_md(text: str) -> str:
    """Add the `license` field and the attribution comment to a rendered SKILL.md."""
    if WATERMARK in text:
        return text
    head, sep, body = text.partition(_FRONTMATTER_END)
    if not text.startswith("---") or not sep:
        return f"{WATERMARK}\n\n{text}"
    if not any(line.startswith("license:") for line in head.splitlines()):
        head += f"\nlicense: {SKILL_LICENSE}"
    return f"{head}{sep}\n{WATERMARK}\n{body}"


def watermark_aux(text: str) -> str:
    """Prefix a supporting skill file (no frontmatter) with the attribution comment."""
    if WATERMARK in text:
        return text
    return f"{WATERMARK}\n\n{text}"
