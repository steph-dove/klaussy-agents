"""Every skill's TEST.md: parsed on every run, executed only when evals are opted in.

The structural tests are free and run in normal CI, so a skill can't ship
without cases and a typo in a directive can't silently skip a check. The live
cases cost a model call each; run one skill's with
`KLAUSSY_RUN_EVALS=1 pytest tests/evals/test_skill_cases.py -k <skill>`.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness
import pytest
import skill_cases

from klaussy.skills import SKILL_NAMES

CASES = skill_cases.load_all()

# A skill whose behavior is driven end to end in tests/e2e/ doesn't need a
# prompt case restating it; those files name their skill in a SKILL constant.
E2E_COVERED = {
    m.group(1)
    for path in (Path(__file__).parent.parent / "e2e").glob("test_*.py")
    if (m := re.search(r'^SKILL = "([^"]+)"', path.read_text(), re.M))
}


def test_every_skill_is_covered():
    have = {p.parent.name for p in skill_cases.SKILLS_DIR.glob("*/TEST.md")}
    uncovered = set(SKILL_NAMES) - have - E2E_COVERED
    assert not uncovered, f"skills with neither a TEST.md nor an e2e test: {uncovered}"
    assert not have - set(SKILL_NAMES), f"TEST.md for unknown skills: {have - set(SKILL_NAMES)}"


def test_the_e2e_markers_name_real_skills():
    assert E2E_COVERED, "no e2e test declares the skill it covers"
    assert not E2E_COVERED - set(SKILL_NAMES), f"unknown skills: {E2E_COVERED - set(SKILL_NAMES)}"


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_each_skill_has_at_least_two_cases(skill):
    if skill in E2E_COVERED:
        pytest.skip(f"{skill} is driven end to end in tests/e2e/")
    assert sum(c.skill == skill for c in CASES) >= 2


def test_parser_reads_aux_files():
    text = "## case: a\n### aux\n- waiting.md\n### context\nx\n### expect\n- contains: ok\n"
    [case] = skill_cases.parse("demo", text)
    assert case.aux == ["waiting.md"]


def test_parser_ignores_headings_inside_fences():
    text = (
        "## case: fenced\n### context\n```md\n## case: not-a-case\n### expect\n```\n"
        "### expect\n- contains: ok\n"
    )
    [case] = skill_cases.parse("demo", text)
    assert "## case: not-a-case" in case.context
    assert case.expect == [("contains", "ok")]


@pytest.mark.parametrize(
    "bad",
    [
        "## case: a\n### context\nx\n### expect\n- contians: y\n",
        "## case: a\n### context\nx\n### expect\n- max lines: many\n",
        "## case: a\n### context\nx\n### expect\n",
        "## case: a\n### expect\n- contains: y\n",
    ],
    ids=["typo", "non-integer", "no-expectations", "no-context"],
)
def test_parser_rejects_malformed_cases(bad):
    with pytest.raises(ValueError):
        skill_cases.parse("demo", bad)


def _one_case(expect: str) -> skill_cases.Case:
    [case] = skill_cases.parse("demo", f"## case: a\n### context\nx\n### expect\n{expect}\n")
    return case


def test_not_commands_ignores_a_command_named_in_prose():
    case = _one_case("- not commands: git rebase --onto")
    rejected = "```\ngt stack restack\n```\n\nRaw `git rebase --onto` would desync Graphite."
    assert skill_cases.check(case, rejected) == []
    assert skill_cases.check(case, "```sh\ngit rebase --onto main\n```") != []


def test_not_commands_reads_prompt_and_standalone_code_lines():
    case = _one_case("- not commands: git push")
    assert skill_cases.check(case, "$ git push --force") != []
    assert skill_cases.check(case, "- `git push`") != []
    assert skill_cases.check(case, "Don't run git push until CI is green.") == []


def test_not_commands_ignores_a_comment_line_inside_a_block():
    case = _one_case("- not commands: --theirs")
    resolved_by_hand = "```\n# resolve by hand, not --theirs\ngit add src/config.py\n```"
    assert skill_cases.check(case, resolved_by_hand) == []
    assert skill_cases.check(case, "```\ngit checkout --theirs src/config.py\n```") != []


def test_not_commands_sees_an_unterminated_fence():
    case = _one_case("- not commands: git push")
    assert skill_cases.check(case, "```\ngit push --force") != []


def test_check_reports_each_failed_expectation():
    [case] = skill_cases.parse(
        "demo",
        "## case: a\n### context\nx\n### expect\n"
        "- contains: alpha | beta\n- not contains: gamma\n- max lines: 1\n",
    )
    assert skill_cases.check(case, "Beta") == []
    assert len(skill_cases.check(case, "gamma\ndelta")) == 3


@harness.requires_eval_env
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_skill_case(case):
    out = harness.run_skill(case.skill, case.context, instruction=case.instruction, aux=case.aux)
    failures = skill_cases.check(case, out)
    assert not failures, f"{case.id}: {failures}\n--- output ---\n{out}"
