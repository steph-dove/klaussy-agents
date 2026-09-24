"""A skill must be allowed to run the commands its own body tells it to run.

Three separate bugs have been this shape: a skill instructed to run `klaussy
base` whose `allowed-tools` only granted `git`, the `{{BASE_RESOLUTION}}` token
that never rendered for nine agents, and a `python -m klaussy` fallback added to
skills forbidden from running it. None of them failed anything. The skill loads,
the model reads an instruction it cannot carry out, and quietly does something
else.

These run on the rendered skills, which is where the mismatch actually shows up.
"""

from __future__ import annotations

import re
import sys
from importlib import resources
from pathlib import Path

import pytest

from klaussy.agents.base import build_skill_payloads
from klaussy.skills import SKILL_NAMES, SKILL_TEMPLATE_ROOT

sys.path.insert(0, str(Path(__file__).resolve().parent / "evals"))

# A klaussy subcommand the skill runs itself. The backtick is required, or this
# matches prose like "klaussy isn't on PATH". `humanize` is excluded: prose
# skills name it to point at that skill, not to shell out.
_KLAUSSY_CMD = re.compile(r"`klaussy ([a-z][a-z-]+)")
_DELEGATED = {"humanize", "ships", "settings"}

# Bare `Bash` allows anything; otherwise the grant has to name the command.
_BARE_BASH = re.compile(r"(^|\s)Bash(\s|$)")


@pytest.fixture(scope="module")
def skills():
    return {p.skill: p for p in build_skill_payloads(repo=Path.cwd())}


def _runs_klaussy(body: str) -> set[str]:
    return set(_KLAUSSY_CMD.findall(body)) - _DELEGATED


def _may_run(allowed: str, command: str) -> bool:
    if _BARE_BASH.search(allowed):
        return True
    return f"Bash(klaussy {command}" in allowed


def test_every_klaussy_command_a_skill_runs_is_granted(skills):
    gaps: list[str] = []
    for name, payload in sorted(skills.items()):
        allowed = payload.allowed_tools or ""
        for command in sorted(_runs_klaussy(payload.body)):
            if not _may_run(allowed, command):
                gaps.append(f"{name}: runs `klaussy {command}` but allowed-tools is {allowed!r}")
    assert not gaps, "skills told to run a command they cannot run:\n" + "\n".join(gaps)


def test_the_module_fallback_is_granted_wherever_it_is_offered(skills):
    """The fallback is worthless in a skill whose grant forbids it.

    That is how it shipped the first time: added to the prose of five skills
    whose `allowed-tools` named only `git` and specific `klaussy` subcommands.
    """
    gaps = [
        f"{name}: offers `python -m klaussy` but allowed-tools is {payload.allowed_tools!r}"
        for name, payload in sorted(skills.items())
        if "python -m klaussy" in payload.body
        and not _BARE_BASH.search(payload.allowed_tools or "")
        and "python -m klaussy" not in (payload.allowed_tools or "")
    ]
    assert not gaps, "\n".join(gaps)


def test_every_skill_that_runs_the_cli_offers_the_fallback(skills):
    """A missing console script is the common pipx failure, not an exotic one."""
    missing = [
        f"{name}: runs {sorted(_runs_klaussy(payload.body))} with no `python -m klaussy` fallback"
        for name, payload in sorted(skills.items())
        if _runs_klaussy(payload.body) and "python -m klaussy" not in payload.body
    ]
    assert not missing, "\n".join(missing)


def test_no_skill_cuts_a_branch_from_the_scaffolded_base():
    """`{{BASE_BRANCH}}` as a git start point is the bug #69 set out to kill.

    A prose mention of the configured base is fine. A start point is not: the
    scaffolded literal goes stale, and a branch cut from the wrong commit makes
    every range measured against it wrong too.

    Reads the templates, not the payloads: substitution has already turned the
    token into a branch name by then, which is exactly how the first version of
    this test passed with the bug reintroduced.
    """
    start_point = re.compile(r"(worktree add|checkout -b|switch -c)\s[^\n`]*\{\{BASE_BRANCH\}\}")
    root = resources.files("klaussy").joinpath(SKILL_TEMPLATE_ROOT)
    offenders = [
        skill
        for skill in SKILL_NAMES
        if start_point.search(root.joinpath(skill, "SKILL.md.tmpl").read_text())
    ]
    assert not offenders, f"these cut a branch from the scaffolded base: {offenders}"


def test_new_worktree_resolves_the_base_rather_than_baking_it(skills):
    body = skills["new-worktree"].body
    assert "Resolve the base first" in body, "new-worktree lost its base resolution"
    assert "-b <branch-name> <base>" in body, "the worktree start point is not the resolved base"


@pytest.mark.parametrize(
    "skill",
    ["review", "pr", "explain", "security-audit", "test", "qa", "fix", "split-pr", "new-worktree"],
)
def test_range_skills_carry_the_base_resolution_block(skills, skill):
    assert "Resolve the base first" in skills[skill].body
