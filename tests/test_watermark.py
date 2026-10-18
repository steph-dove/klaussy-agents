"""Every skill file klaussy writes, for every agent, carries the attribution watermark."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from klaussy.agents.backends import BACKENDS
from klaussy.agents.base import _split_frontmatter
from klaussy.checklist import generate_checklist
from klaussy.watermark import SKILL_LICENSE, WATERMARK, watermark_aux, watermark_skill_md


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("watermark")
    (repo / "pyproject.toml").write_text('name = "demo"\n')
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for backend in BACKENDS.values():
        backend.run_skills(repo, force=True, base_branch="main", review_template=None)
    return repo


def _skill_files(repo: Path) -> list[Path]:
    return [p for p in repo.rglob("*.md") if "skills" in p.relative_to(repo).parts]


def test_every_skill_file_is_watermarked(scaffolded: Path):
    files = _skill_files(scaffolded)
    assert files
    missing = [str(p.relative_to(scaffolded)) for p in files if WATERMARK not in p.read_text()]
    assert not missing, "skill files without the watermark:\n  " + "\n  ".join(missing)


def test_every_skill_md_declares_the_license(scaffolded: Path):
    for path in scaffolded.rglob("SKILL.md"):
        fm, body = _split_frontmatter(path.read_text())
        assert fm.get("license") == SKILL_LICENSE, path
        assert fm.get("name"), path
        assert body.startswith(WATERMARK), path


def test_checklist_review_skill_is_watermarked(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# demo\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    out = generate_checklist(repo=tmp_path, force=True)
    assert WATERMARK in out.read_text()
    for sibling in out.parent.glob("*.md"):
        assert WATERMARK in sibling.read_text(), sibling.name


def test_watermarking_is_idempotent():
    md = "---\nname: x\ndescription: y\n---\n\nbody\n"
    once = watermark_skill_md(md)
    assert watermark_skill_md(once) == once
    assert once.count("license:") == 1
    assert watermark_aux(watermark_aux("text")) == watermark_aux("text")


def test_existing_license_field_is_kept():
    md = "---\nname: x\nlicense: Apache-2.0\n---\nbody\n"
    fm, _ = _split_frontmatter(watermark_skill_md(md))
    assert fm["license"] == "Apache-2.0"


def test_installable_root_skills_are_watermarked():
    root = Path(__file__).resolve().parent.parent / "skills"
    paths = sorted(root.glob("*/SKILL.md"))
    assert paths
    for path in paths:
        text = path.read_text()
        assert watermark_skill_md(text) == text, path
        assert _split_frontmatter(text)[0].get("license") == SKILL_LICENSE, path
