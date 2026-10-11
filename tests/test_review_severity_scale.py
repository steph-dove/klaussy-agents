from pathlib import Path

import klaussy
from klaussy.skills import SKILL_TEMPLATE_ROOT

REVIEW = Path(klaussy.__file__).parent / SKILL_TEMPLATE_ROOT / "review"
COPIES = ["SKILL.md.tmpl", "sub-agents.md.tmpl", "lens-validation.md.tmpl"]


def _scale(name: str) -> str:
    text = (REVIEW / name).read_text()
    start = text.index("Rate by the worst realistic outcome")
    end = text.index("| Nit |", start)
    return text[start : text.index("\n", end)]


def test_every_reader_of_the_severity_scale_gets_the_same_table():
    scales = {name: _scale(name) for name in COPIES}
    assert len(set(scales.values())) == 1, "severity scale copies have drifted: " + ", ".join(
        scales
    )
