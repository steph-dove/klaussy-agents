"""Shared primitives for multi-agent scaffolding.

klaussy's skills, conventions, and permissions originate in Claude Code's
formats. Every other supported agent (Gemini CLI, Cursor, Codex, Copilot) now
reads the same open Agent Skills `SKILL.md` spec, so the per-agent work reduces
to: (1) where files land, and (2) light, capability-driven adaptation of the
skill bodies (Claude's ```! dynamic-shell blocks, parallel sub-agent
orchestration, and plan mode don't all exist everywhere).

`CapabilityProfile` captures those differences; `build_skill_payloads` produces
the canonical, fully-substituted skill content once; concrete backends in this
package format and place it per agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from klaussy.checklist import build_enrichment_block
from klaussy.skills import HUMANIZE_BLOCK, SKILL_NAMES, sanitize_skill_namespace


@dataclass(frozen=True)
class CapabilityProfile:
    """How to adapt Claude-authored skill bodies for a target agent.

    `skills_root` is the repo-relative directory the agent reads `SKILL.md`
    folders from. The boolean flags drive `render.adapt_body`.

    `subagents` and `plan_mode` mean "the skill body's Claude-native syntax for
    this is correct as-is for this agent" — True only for Claude. They do NOT
    claim other agents lack the capability: as of 2026 Cursor (`Task`), Codex
    (`spawn_agent`), Gemini (subagents) and Copilot (`task`) all have a
    model-invocable parallel sub-agent tool, and most have a plan/approval mode.
    When False, a translation banner tells the agent to map Claude's
    `Agent`/`subagent_type` (or `ExitPlanMode`) wording to its own equivalent,
    falling back to sequential only if it genuinely has none.

    `subagent_mechanism` / `plan_mechanism`, when set, replace that generic
    "use your equivalent, else go sequential" banner with an affirmative,
    agent-specific instruction — for an agent known to have real parallel
    sub-agents (e.g. opencode's `@`-mention subagents) or a real plan mode
    (opencode's Plan agent), so the skill fans out for real instead of hedging.
    Left None for agents whose exact mechanism we don't want to assert.

    `dynamic_shell` is True when the agent executes ```! blocks at load time
    (Claude, Gemini); when False they're rewritten to plain run-instructions.
    """

    key: str
    label: str
    skills_root: str
    dynamic_shell: bool
    subagents: bool
    plan_mode: bool
    keep_allowed_tools: bool
    keep_disable_invocation: bool
    subagent_mechanism: str | None = None
    plan_mechanism: str | None = None


@dataclass
class SkillPayload:
    """One skill's canonical content, fully substituted and enrichment-applied."""

    skill: str
    name: str
    description: str
    allowed_tools: str | None
    disable_invocation: bool
    body: str
    aux_files: dict[str, str] = field(default_factory=dict)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a `SKILL.md` into (frontmatter dict, body).

    The frontmatter is simple key: value YAML (no nesting), which is all the
    skill templates use. Returns an empty dict and the original text if no
    frontmatter block is present.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")

    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, body


def build_skill_payloads(
    *,
    repo: Path,
    base_branch: str = "main",
    review_template: Path | None = None,
) -> list[SkillPayload]:
    """Build canonical payloads for every bundled skill.

    Loads each template, substitutes {{REPO}} / {{BASE_BRANCH}} /
    {{REPO_SPECIFIC_CHECKS}}, and parses out frontmatter. The review enrichment
    is computed once here (shared with the Claude `generate_checklist` path via
    `build_enrichment_block`) so every agent's review skill is identically
    enriched. Auxiliary skill files (e.g. review's `sub-agents.md`) are carried
    on the payload, also fully substituted.
    """
    repo = repo.resolve()
    namespace = sanitize_skill_namespace(repo.name)
    enrichment = build_enrichment_block(repo)
    templates = resources.files("klaussy").joinpath("templates/skills")

    def substitute(text: str) -> str:
        return (
            text.replace("{{REPO_SPECIFIC_CHECKS}}", enrichment)
            .replace("{{BASE_BRANCH}}", base_branch)
            .replace("{{REPO}}", namespace)
            .replace("{{HUMANIZE}}", HUMANIZE_BLOCK)
        )

    payloads: list[SkillPayload] = []
    for skill in SKILL_NAMES:
        skill_dir = templates.joinpath(skill)

        aux_files: dict[str, str] = {}
        skill_md = ""
        for template_file in skill_dir.iterdir():
            if (
                skill == "review"
                and template_file.name == "SKILL.md"
                and review_template is not None
            ):
                content = review_template.read_text()
            else:
                content = template_file.read_text()
            content = substitute(content)
            if template_file.name == "SKILL.md":
                skill_md = content
            else:
                aux_files[template_file.name] = content

        fm, body = _split_frontmatter(skill_md)
        payloads.append(
            SkillPayload(
                skill=skill,
                name=fm.get("name", f"{namespace}-{skill}"),
                description=fm.get("description", ""),
                allowed_tools=fm.get("allowed-tools"),
                disable_invocation=fm.get("disable-model-invocation", "").lower() == "true",
                body=body,
                aux_files=aux_files,
            )
        )
    return payloads


# --- Canonical conventions (CLAUDE.md + .claude/rules) -----------------------


@dataclass
class ScopedRule:
    """A path-scoped rule bucket from `.claude/rules/<stem>.md`."""

    stem: str
    globs: list[str]
    body: str


@dataclass
class ConventionsDoc:
    """The repo's generated conventions: project-wide text + path-scoped rules."""

    project_wide: str
    rules: list[ScopedRule]


def read_canonical_conventions(repo: Path) -> ConventionsDoc | None:
    """Read CLAUDE.md (+ `.claude/rules/*.md`) as the canonical conventions source.

    Returns None if no CLAUDE.md exists at either the repo root or `.claude/`.
    The Claude backend generates these via klaussy-repo-conventions; the other backends
    convert this doc into their own native conventions file(s).
    """
    repo = repo.resolve()
    claude_md: Path | None = None
    for candidate in (repo / "CLAUDE.md", repo / ".claude" / "CLAUDE.md"):
        if candidate.exists():
            claude_md = candidate
            break
    if claude_md is None:
        return None

    rules: list[ScopedRule] = []
    rules_dir = repo / ".claude" / "rules"
    if rules_dir.exists():
        for rules_file in sorted(rules_dir.glob("*.md")):
            text = rules_file.read_text()
            if not text.startswith("---"):
                continue
            end = text.find("\n---", 3)
            if end == -1:
                continue
            frontmatter = text[3:end]
            body = text[end + 4 :].lstrip("\n")
            # The generated body opens with its own "# Rules for <glob>" heading.
            # Backends that re-wrap the rule (nested AGENTS.md/GEMINI.md, inline
            # conventions) add their own heading, so a retained one produced a
            # duplicate header. Strip it here — the glob lives in `globs` anyway.
            body = re.sub(r"^# Rules for [^\n]*\n+", "", body, count=1)
            globs = re.findall(r'-\s*"([^"]+)"', frontmatter)
            if not globs:
                globs = re.findall(r"-\s*'([^']+)'", frontmatter)
            if not globs:
                continue
            rules.append(ScopedRule(stem=rules_file.stem, globs=globs, body=body))

    return ConventionsDoc(project_wide=claude_md.read_text(), rules=rules)
