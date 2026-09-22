"""Parse and check the per-skill eval cases in `tests/evals/skills/<skill>/TEST.md`.

A TEST.md holds cases in Markdown so they read like documentation:

    ## case: <slug>
    ### instruction      (optional; prepended to the context)
    ### aux              (optional; sibling files the skill would have read)
    ### context          (what the skill would have gathered with tools)
    ### expect           (one directive per bullet)

Headings inside fenced code blocks are content, not structure, so a context can
carry a diff or a Markdown file verbatim. Directive values separate with ` | `
and match case-insensitively:

    - contains: a | b          at least one appears
    - contains all: a | b      every one appears
    - not contains: a | b      none appears
    - not commands: a | b      none appears in a command the output *prescribes*
    - matches: <regex>         re.search, case-sensitive; start with (?i) to opt out
    - max sentences: N
    - max lines: N             non-blank lines
    - no ai tells
    - conventional subject     first non-blank line is a Conventional Commit

The files live here rather than beside the templates because everything under
`skill-templates/` ships in the wheel and must carry the `.tmpl` suffix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import harness

SKILLS_DIR = Path(__file__).parent / "skills"

_VALUED = {
    "contains",
    "contains all",
    "not contains",
    "not commands",
    "matches",
    "max sentences",
    "max lines",
}
_FLAGS = {"no ai tells", "conventional subject"}
_SECTIONS = {"instruction", "aux", "context", "expect"}
_CASE = re.compile(r"^## case: (\S+)\s*$")
_SECTION = re.compile(r"^### (\w+)\s*$")
_FENCE = re.compile(r"^(```|~~~)")

# The three shapes that count as "run this". An unterminated fence still counts,
# so a truncated answer can't launder a command past the ban.
_FENCED_BLOCK = re.compile(r"^(?:```|~~~)[^\n]*\n(.*?)(?:^(?:```|~~~)|\Z)", re.M | re.S)
_CODE_ONLY_LINE = re.compile(r"^[ \t]*(?:[-*+]\s+)?`([^`]+)`[.;:]?[ \t]*$", re.M)
_PROMPT_LINE = re.compile(r"^[ \t]*[$%>][ \t]+(\S.*)$", re.M)
# A whole-line `#` comment inside a block is the model talking, not a command:
# "# not --theirs, resolve by hand" must not trip a ban on `--theirs`.
_COMMENT_LINE = re.compile(r"^[ \t]*#.*$", re.M)


@dataclass
class Case:
    skill: str
    name: str
    context: str
    instruction: str | None
    expect: list[tuple[str, str]] = field(default_factory=list)
    aux: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.skill}::{self.name}"


def parse(skill: str, text: str) -> list[Case]:
    """Parse one TEST.md. Raises ValueError on anything malformed."""
    cases: list[Case] = []
    name: str | None = None
    section: str | None = None
    buf: dict[str, list[str]] = {}
    in_fence = False

    def flush() -> None:
        if name is None:
            return
        context = "\n".join(buf.get("context", [])).strip()
        if not context:
            raise ValueError(f"{skill}::{name} has no context")
        instruction = "\n".join(buf.get("instruction", [])).strip() or None
        aux = [x.strip("- ").strip() for x in buf.get("aux", []) if x.strip()]
        expect = [_directive(skill, name, line) for line in buf.get("expect", []) if line.strip()]
        if not expect:
            raise ValueError(f"{skill}::{name} has no expectations")
        cases.append(Case(skill, name, context, instruction, expect, aux))

    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and (m := _CASE.match(line)):
            flush()
            name, section, buf = m.group(1), None, {}
            continue
        if not in_fence and name is not None and (m := _SECTION.match(line)):
            section = m.group(1)
            if section not in _SECTIONS:
                raise ValueError(f"{skill}::{name} has unknown section {section!r}")
            continue
        if section is not None:
            buf.setdefault(section, []).append(line)
    flush()

    names = [c.name for c in cases]
    if len(names) != len(set(names)):
        raise ValueError(f"{skill} has duplicate case names")
    return cases


def _directive(skill: str, case: str, line: str) -> tuple[str, str]:
    body = line.strip()
    if not body.startswith("- "):
        raise ValueError(f"{skill}::{case} expect line is not a bullet: {line!r}")
    body = body[2:].strip()
    if body in _FLAGS:
        return body, ""
    key, sep, value = body.partition(":")
    key, value = key.strip(), value.strip()
    if not sep or key not in _VALUED or not value:
        raise ValueError(f"{skill}::{case} has unknown directive {body!r}")
    if key.startswith("max") and not value.isdigit():
        raise ValueError(f"{skill}::{case} {key} needs an integer, got {value!r}")
    if key == "matches":
        re.compile(value)
    return key, value


def load_all() -> list[Case]:
    cases: list[Case] = []
    for path in sorted(SKILLS_DIR.glob("*/TEST.md")):
        cases.extend(parse(path.parent.name, path.read_text()))
    return cases


def prescribed_commands(output: str) -> str:
    """Return only the parts of `output` that tell the reader to run something.

    Naming a command in prose to rule it out ("using raw `git rebase --onto`
    would leave Graphite's metadata stale") is the skill getting it right, so a
    plain substring ban fails the correct answer. Only a fenced block, a line
    that is nothing but one inline-code span, and a shell-prompt line read as
    prescriptions; everything else is prose the ban ignores.

    An output that prescribes nothing in those shapes yields "", so the ban
    passes vacuously. Pair `not commands` with a `contains`/`matches` that pins
    the command you *do* want, or a bare unfenced command line slips through.
    """
    blocks = [_COMMENT_LINE.sub("", b) for b in _FENCED_BLOCK.findall(output)]
    prose = _FENCED_BLOCK.sub("\n", output)
    return "\n".join(blocks + _CODE_ONLY_LINE.findall(prose) + _PROMPT_LINE.findall(prose))


def check(case: Case, output: str) -> list[str]:
    """Return one message per failed expectation; empty means the case passed."""
    low = output.lower()
    failures: list[str] = []
    for key, value in case.expect:
        options = [v.strip().lower() for v in value.split(" | ")]
        if key == "contains" and not any(o in low for o in options):
            failures.append(f"none of {options} appears")
        elif key == "contains all":
            failures += [f"missing {o!r}" for o in options if o not in low]
        elif key == "not contains":
            failures += [f"contains forbidden {o!r}" for o in options if o in low]
        elif key == "not commands":
            commands = prescribed_commands(output).lower()
            failures += [f"prescribes forbidden {o!r}" for o in options if o in commands]
        elif key == "matches" and not re.search(value, output):
            failures.append(f"no match for /{value}/")
        elif key == "max sentences" and harness.count_sentences(output) > int(value):
            failures.append(f"{harness.count_sentences(output)} sentences, budget {value}")
        elif key == "max lines":
            lines = [x for x in output.splitlines() if x.strip()]
            if len(lines) > int(value):
                failures.append(f"{len(lines)} lines, budget {value}")
        elif key == "no ai tells" and (tells := harness.ai_tells_present(output)):
            failures.append(f"AI tells: {tells}")
        elif key == "conventional subject" and not harness.is_conventional_subject(
            harness.first_nonempty_line(output)
        ):
            failures.append(f"not a conventional subject: {harness.first_nonempty_line(output)!r}")
    return failures
