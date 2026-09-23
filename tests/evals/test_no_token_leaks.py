"""No skill reaches a model with an unresolved `{{TOKEN}}` in it.

Both eval harnesses render skill bodies themselves, and a token they don't know
doesn't fail: it arrives as literal `{{...}}` text in the prompt. That is how
`{{FORGE}}` and `{{BASE_RESOLUTION}}` came to sit in the e2e harness's output,
unnoticed, because both suites are opt-in and neither runs in CI.

This is free and always runs, which is the point: it is the guard those two
suites can't be for themselves.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import harness
import pytest

from klaussy.skills import SKILL_NAMES

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))

import e2e_harness  # noqa: E402  (needs the path above)

_TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")

_RENDERERS = {"evals": harness.load_skill_body, "e2e": e2e_harness.load_skill_body}


@pytest.mark.parametrize("renderer", sorted(_RENDERERS))
@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_no_unresolved_token_reaches_the_model(skill, renderer):
    leaked = sorted(set(_TOKEN.findall(_RENDERERS[renderer](skill))))
    assert not leaked, f"{renderer} harness leaves {leaked} in {skill}"


def test_both_harnesses_render_every_shipped_skill():
    """A skill the harness can't load would skip silently above."""
    for name, render in _RENDERERS.items():
        for skill in SKILL_NAMES:
            assert render(skill).strip(), f"{name} harness rendered {skill} empty"
