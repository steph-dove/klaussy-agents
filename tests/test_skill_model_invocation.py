"""A skill that says "Use when…" must not then refuse model invocation.

A "Use when…" description is the auto-trigger heuristic, so pairing it with
`disable-model-invocation: true` leaves the skill unreachable by name in prose.
Side-effect gates belong in the skill body (confirm the plan, never publish or
rewrite history without approval), which keeps the skill reachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from klaussy import skills as skills_mod

TEMPLATE_ROOT = Path(skills_mod.__file__).parent / "templates" / "skill-templates"


def _skill_templates() -> list[Path]:
    return sorted(TEMPLATE_ROOT.glob("*/SKILL.md.tmpl"))


SKILL_TEMPLATES = _skill_templates()


def _frontmatter(path: Path) -> str:
    text = path.read_text()
    if not text.startswith("---\n"):
        return ""
    return text.split("---\n", 2)[1]


def test_skill_templates_are_discovered():
    """Guard the guard: an empty glob would make the check below vacuous."""
    assert len(SKILL_TEMPLATES) >= 20, f"expected the skill templates, found {SKILL_TEMPLATES}"


@pytest.mark.parametrize(
    "path", SKILL_TEMPLATES, ids=[p.parent.name for p in SKILL_TEMPLATES]
)
def test_use_when_skills_stay_model_invocable(path: Path):
    front = _frontmatter(path)
    if "disable-model-invocation: true" not in front:
        return
    description = next(
        (line for line in front.splitlines() if line.startswith("description:")), ""
    )
    assert not description.startswith("description: Use when"), (
        f"{path.parent.name} advertises itself for auto-trigger "
        f'("Use when…") but sets disable-model-invocation: true, so the model '
        f"cannot reach it. Gate side effects in the body instead."
    )
