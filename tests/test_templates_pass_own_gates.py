"""Every guard template must pass the gates it installs, judged whole-file.

A scaffolded repo receives these files entire, so every line lands in that first
commit's diff and the gate judges all of it. In this repo the same gate is
diff-scoped, which hides a violation nobody has touched since — so a template can
be clean here and block the first commit in every repo that installs it. Three
releases running shipped exactly that (0.18.1's three-sentence comment, 0.19.0's
four-line one), each found only by regenerating examples. This catches them here.
"""

from pathlib import Path

import pytest

from klaussy import hooks as hooks_mod
from klaussy.comment_lint import analyze as analyze_comments
from klaussy.import_lint import analyze as analyze_imports

TEMPLATES = Path(hooks_mod.__file__).parent / "templates"


def _template_sources() -> list[Path]:
    return sorted(p for p in TEMPLATES.rglob("*.py") if "__pycache__" not in p.parts)


TEMPLATE_SOURCES = _template_sources()


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(TEMPLATES)) for p in paths]


def test_templates_are_discovered():
    """Guard the guard: an empty glob would make every check below vacuous."""
    assert len(TEMPLATE_SOURCES) >= 8, f"expected the hook templates, found {TEMPLATE_SOURCES}"


@pytest.mark.parametrize("path", TEMPLATE_SOURCES, ids=_ids(TEMPLATE_SOURCES))
def test_template_passes_comment_lint(path: Path):
    findings = analyze_comments(str(path), path.read_text())
    assert not findings, (
        "template would block the first commit in a repo that installs it:\n"
        + "\n".join(f.render() for f in findings)
    )


@pytest.mark.parametrize("path", TEMPLATE_SOURCES, ids=_ids(TEMPLATE_SOURCES))
def test_template_passes_import_lint(path: Path):
    findings = analyze_imports(str(path), path.read_text())
    assert not findings, (
        "template would block the first commit in a repo that installs it:\n"
        + "\n".join(f.render() for f in findings)
    )
