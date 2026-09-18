"""Tests for `gh skill install` compatibility.

`gh skill install` (and anything else following the Agent Skills spec) discovers
skills by the `skills/*/SKILL.md` convention, matching that path segment anywhere
in the tree, and the spec defines no way to opt a directory out.

klaussy's 28 skill *templates* used to live at `src/klaussy/templates/skills/`,
which matched. gh listed all of them as installable and then failed on every one:
their frontmatter carries `name: {{REPO}}-review`, and a leading `{` opens a YAML
flow mapping, so the document does not parse. Users saw 28 broken entries beside
the two real skills.

Two things keep it fixed, and these tests hold both. The templates sit under
`SKILL_TEMPLATE_ROOT`, which contains no `skills` path segment; and every file
under it carries `TEMPLATE_SUFFIX`, so `SKILL.md.tmpl` cannot match the
convention whatever directory it ends up in. The suffix is the load-bearing one
— the directory name only documents the intent.

The suffix is stripped on the way out, so a scaffolded repo still gets plain
`SKILL.md`, `sub-agents.md` and `comment-cleanup.md`. klaussy-desktop reads
those generated names directly (`main/state/precommit-review.js`), so the
emitted filenames are a contract, not an implementation detail.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from klaussy.skills import (
    SKILL_TEMPLATE_ROOT,
    TEMPLATE_SUFFIX,
    iter_skill_templates,
    template_output_name,
)

REPO = Path(__file__).resolve().parent.parent
PUBLISHED_SKILLS = REPO / "skills"

# https://agentskills.io/specification
MAX_NAME = 64
MAX_DESCRIPTION = 1024


def _tracked_skill_md() -> list[Path]:
    """Every SKILL.md git tracks, excluding hidden directories.

    gh skips hidden directories unless `--allow-hidden-dirs` is passed, so the
    per-agent output under `examples/*/.claude/skills/` and this repo's own
    dogfooded `.claude/skills/` are out of scope.
    """
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*SKILL.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        REPO / rel
        for rel in out.split("\0")
        if rel and not any(part.startswith(".") for part in Path(rel).parts)
    ]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path}: no frontmatter"
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm)


# --- discovery ---------------------------------------------------------------


TEMPLATE_DIR = REPO / "src" / "klaussy" / SKILL_TEMPLATE_ROOT


def test_skill_templates_are_not_under_a_discoverable_path():
    # A `skills` segment anywhere in this path puts 28 unsubstituted templates
    # back into `gh skill install`'s list.
    assert "skills" not in Path(SKILL_TEMPLATE_ROOT).parts
    assert TEMPLATE_DIR.is_dir()


def test_every_template_file_carries_the_suffix():
    # The real guard: a file named SKILL.md.tmpl is not discoverable no matter
    # which directory it sits in, so this survives someone renaming the folder.
    unmarked = [
        p.relative_to(TEMPLATE_DIR).as_posix()
        for p in TEMPLATE_DIR.rglob("*")
        if p.is_file() and not p.name.endswith(TEMPLATE_SUFFIX)
    ]
    assert not unmarked, f"unmarked template files: {unmarked}"


def test_no_template_is_named_exactly_skill_md():
    assert not list(TEMPLATE_DIR.rglob("SKILL.md"))


def test_suffix_is_stripped_for_the_emitted_name():
    # klaussy-desktop reads `.claude/skills/<repo>-precommit/SKILL.md` and its
    # sibling `comment-cleanup.md` by those exact names. Renaming the templates
    # must not change what lands in a scaffolded repo.
    assert template_output_name("SKILL.md" + TEMPLATE_SUFFIX) == "SKILL.md"
    assert template_output_name("comment-cleanup.md.tmpl") == "comment-cleanup.md"
    assert template_output_name("sub-agents.md.tmpl") == "sub-agents.md"
    # Idempotent on an already-stripped name.
    assert template_output_name("SKILL.md") == "SKILL.md"


def test_emitted_names_round_trip_for_every_template():
    for skill_dir in sorted(p for p in TEMPLATE_DIR.iterdir() if p.is_dir()):
        emitted = [template_output_name(f.name) for f in iter_skill_templates(skill_dir)]
        assert "SKILL.md" in emitted, f"{skill_dir.name} emits no SKILL.md"
        assert not any(n.endswith(TEMPLATE_SUFFIX) for n in emitted)


def test_iter_skill_templates_skips_unmarked_files(tmp_path):
    # A stray .DS_Store or editor backup must not be copied into a user's repo.
    (tmp_path / "SKILL.md.tmpl").write_text("x")
    (tmp_path / ".DS_Store").write_text("junk")
    (tmp_path / "SKILL.md.bak").write_text("junk")
    assert [f.name for f in iter_skill_templates(tmp_path)] == ["SKILL.md.tmpl"]


def test_only_the_published_skills_directory_is_discoverable():
    discoverable = {
        p.parent.parent for p in _tracked_skill_md() if p.parent.parent.name == "skills"
    }
    assert discoverable == {PUBLISHED_SKILLS}, (
        "a new skills/*/SKILL.md path would be offered by `gh skill install`; "
        f"found {sorted(str(p.relative_to(REPO)) for p in discoverable)}"
    )


def test_no_tracked_skill_md_sits_outside_those_two_roots():
    stray = [
        p
        for p in _tracked_skill_md()
        if p.parent.parent != PUBLISHED_SKILLS and SKILL_TEMPLATE_ROOT not in p.as_posix()
    ]
    assert not stray, [str(p.relative_to(REPO)) for p in stray]


# --- substitution tokens stay inside skill templates -------------------------

TEMPLATES = REPO / "src" / "klaussy" / "templates"
TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")


def test_only_skill_templates_carry_substitution_tokens():
    """`{{TOKEN}}` is the skill-template convention and nothing else expands it.

    Hook templates use `"__KLAUSSY_X__"` sentinels instead, replaced as quoted
    Python/JS literals — a mechanism that only reaches baked *values*, never
    comment text. Three `{{REPO}}` tokens had been written into the self-review
    guard and the opencode plugin, so every scaffolded repo shipped a hook whose
    comments read `{{REPO}}-self-review` verbatim.
    """
    offenders = {}
    for path in sorted(TEMPLATES.rglob("*")):
        if not path.is_file() or SKILL_TEMPLATE_ROOT in path.as_posix():
            continue
        found = sorted(set(TOKEN.findall(path.read_text(errors="ignore"))))
        if found:
            offenders[path.relative_to(TEMPLATES).as_posix()] = found
    assert not offenders, (
        "substitution tokens outside the skill templates are never expanded and "
        f"ship to users verbatim: {offenders}"
    )


def test_skill_templates_do_still_use_tokens():
    # Guards the test above against passing because substitution went away.
    review = TEMPLATE_DIR / "review" / ("SKILL.md" + TEMPLATE_SUFFIX)
    assert TOKEN.search(review.read_text())


# --- the published skills hold to the spec -----------------------------------


def _published() -> list[Path]:
    return sorted(PUBLISHED_SKILLS.glob("*/SKILL.md"))


def test_there_are_published_skills():
    assert _published(), "skills/ is empty — nothing for `gh skill install` to find"


@pytest.mark.parametrize("path", _published(), ids=lambda p: p.parent.name)
def test_published_skill_frontmatter_is_valid(path):
    # gh parses this before installing; invalid YAML fails the install outright.
    fm = _frontmatter(path)

    name = fm.get("name")
    assert name == path.parent.name, "spec: name must match the parent directory"
    assert len(name) <= MAX_NAME
    assert all(c.islower() or c.isdigit() or c == "-" for c in name), (
        "spec: lowercase alphanumerics and hyphens only"
    )
    assert not name.startswith("-") and not name.endswith("-")
    assert "--" not in name

    description = fm.get("description", "")
    assert description, "spec: description is required and non-empty"
    assert len(description) <= MAX_DESCRIPTION


@pytest.mark.parametrize("path", _published(), ids=lambda p: p.parent.name)
def test_published_skills_carry_no_unsubstituted_tokens(path):
    # A template token here means a skill template leaked into the installable
    # directory, which is the failure this whole module exists to prevent.
    text = path.read_text()
    assert "{{" not in text, f"{path.name} still contains a substitution token"


# --- the alias reaches every emit path --------------------------------------


def test_alias_is_skipped_when_the_namespace_already_matches():
    from klaussy.skills import describe_with_alias

    assert describe_with_alias("Does a thing.", "review", "klaussy") == "Does a thing."
    assert "klaussy-review" in describe_with_alias("Does a thing.", "review", "payments")


def test_checklist_keeps_the_alias_on_the_review_skill(tmp_path, monkeypatch):
    """`klaussy checklist` rewrites the review skill from the template.

    It is the third emit path for that one skill, after scaffold_skills and
    build_skill_payloads, and it used to strip the alias that `klaussy skills`
    had just added.
    """
    from klaussy.checklist import generate_checklist

    repo = tmp_path / "payments"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text(
        "# CLAUDE.md - payments\n\n## Commands\n\n- **Test**: `pytest`\n"
    )

    out = generate_checklist(repo=repo, force=True, base_branch="main")
    assert "Also known as `klaussy-review`." in out.read_text()
