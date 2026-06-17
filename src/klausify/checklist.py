"""Generate a repo-tailored review skill from CLAUDE.md and .claude/rules/."""

import re
from importlib import resources
from pathlib import Path

from rich.console import Console

from klausify.skills import sanitize_skill_namespace

console = Console()


def _read_review_template() -> str:
    """Read the review skill template."""
    return (
        resources.files("klausify")
        .joinpath("templates/skills/review/SKILL.md")
        .read_text()
    )


def _resolve_claude_md(repo: Path) -> Path | None:
    """Return the canonical CLAUDE.md path, preferring repo root over .claude/.

    Both locations are valid per Claude Code docs; root is canonical for
    Claude Code 2.x and the conventions-cli 1.4.0+ default.
    """
    for candidate in (repo / "CLAUDE.md", repo / ".claude" / "CLAUDE.md"):
        if candidate.exists():
            return candidate
    return None


def _parse_claude_md(claude_md: Path) -> dict[str, list[str]]:
    """Extract project-wide sections from CLAUDE.md for review enrichment.

    Path-scoped rules live in `.claude/rules/*.md` in conventions-cli 1.4.0+
    and are read separately by `_parse_rules_dir`. CLAUDE.md only contains
    project-wide content, so this parser is intentionally simple — collect
    bullets under recognized H2 sections.
    """
    content = claude_md.read_text()
    sections: dict[str, list[str]] = {
        "conventions": [],
        "commands": [],
        "tech_stack": [],
        "pitfalls": [],
    }

    current_section = ""
    for line in content.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("## conventions"):
            current_section = "conventions"
        elif lower.startswith("## commands"):
            current_section = "commands"
        elif lower.startswith("## tech stack"):
            current_section = "tech_stack"
        elif lower.startswith("## known pitfalls"):
            current_section = "pitfalls"
        elif lower.startswith("## "):
            current_section = ""
        elif current_section and stripped.startswith("- "):
            sections[current_section].append(stripped)

    return sections


def _parse_rules_dir(rules_dir: Path) -> list[str]:
    r"""Read `.claude/rules/*.md` files and return path-scoped bullets.

    Each rules file has YAML frontmatter with a `paths:` field (list of
    globs) and a body containing `## Conventions` and/or `## Architecture`
    bullets. Returns bullets formatted as `for \`<glob>\`: <rule>`.
    """
    if not rules_dir.exists():
        return []

    bullets: list[str] = []
    for rules_file in sorted(rules_dir.glob("*.md")):
        text = rules_file.read_text()
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        frontmatter = text[3:end]
        body = text[end + 4:]

        path_matches = re.findall(r'-\s*"([^"]+)"', frontmatter)
        if not path_matches:
            path_matches = re.findall(r"-\s*'([^']+)'", frontmatter)
        if not path_matches:
            continue
        glob_label = ", ".join(f"`{p}`" for p in path_matches)

        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            # Strip `**bold**` markers from the rule body BEFORE composing the
            # output bullet. Otherwise the `**` from the glob pattern (e.g.
            # `src/api/**/*.py`) and the `**` opening the title both feed into
            # _build_convention_checks's bold-strip regex, which greedily
            # pairs them and silently eats the glob.
            rule_body = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped[2:])
            bullets.append(f"- for {glob_label}: {rule_body}")

    return bullets


def _build_convention_checks(conventions: list[str]) -> str:
    """Turn convention bullet points into review check items."""
    if not conventions:
        return ""
    lines = ["### Repo Conventions"]
    for conv in conventions:
        label = re.sub(r"^\-\s*", "", conv)
        label = re.sub(r"\*\*(.+?)\*\*", r"\1", label)
        lines.append(f"- {label}")
    return "\n".join(lines)


def _build_command_checks(commands: list[str]) -> str:
    """Turn command items into verification checks."""
    if not commands:
        return ""
    lines = ["### Verification Commands", "Ensure these pass before approving:"]
    for cmd in commands:
        label = re.sub(r"^\-\s*", "", cmd)
        code_match = re.search(r"`(.+?)`", label)
        if code_match:
            lines.append(f"- `{code_match.group(1)}`")
    return "\n".join(lines)


def _build_pitfall_checks(pitfalls: list[str]) -> str:
    """Turn known pitfalls into review watch items."""
    if not pitfalls:
        return ""
    lines = ["### Known Pitfalls", "Flag if any of these are violated:"]
    for pitfall in pitfalls:
        label = re.sub(r"^\-\s*", "", pitfall)
        label = re.sub(r"\*\*(.+?)\*\*", r"\1", label)
        lines.append(f"- {label}")
    return "\n".join(lines)


def _review_skill_dir(repo: Path) -> str:
    """Return the namespaced review skill directory name."""
    return f"{sanitize_skill_namespace(repo.name)}-review"


def build_enrichment_block(repo: Path) -> str:
    """Compute the repo-specific {{REPO_SPECIFIC_CHECKS}} block for the review skill.

    Parses CLAUDE.md (project-wide sections) and `.claude/rules/*.md` (path-scoped
    rules) into review check items. Returns the empty string when no conventions,
    commands, or pitfalls are found. Shared by `generate_checklist` (Claude path)
    and the multi-agent skill payload builder so every target's review skill gets
    the same enrichment.
    """
    claude_md = _resolve_claude_md(repo)
    if claude_md is None:
        return ""

    sections = _parse_claude_md(claude_md)
    path_scoped_bullets = _parse_rules_dir(repo / ".claude" / "rules")

    project_wide = list(sections["conventions"])
    project_wide.extend(path_scoped_bullets)

    enrichments: list[str] = []
    conv_checks = _build_convention_checks(project_wide)
    if conv_checks:
        enrichments.append(conv_checks)
    cmd_checks = _build_command_checks(sections["commands"])
    if cmd_checks:
        enrichments.append(cmd_checks)
    pitfall_checks = _build_pitfall_checks(sections["pitfalls"])
    if pitfall_checks:
        enrichments.append(pitfall_checks)

    return "\n\n".join(enrichments) if enrichments else ""


def generate_checklist(*, repo: Path, force: bool = False, base_branch: str = "main") -> Path:
    """Generate a review skill enriched with CLAUDE.md and .claude/rules/ findings."""
    repo = repo.resolve()
    claude_md = _resolve_claude_md(repo)

    if claude_md is None:
        console.print(
            "[red]✗ CLAUDE.md not found at ./CLAUDE.md or ./.claude/CLAUDE.md. "
            "Run `klausify init` first.[/red]"
        )
        raise SystemExit(1)

    skill_dir = repo / ".claude" / "skills" / _review_skill_dir(repo)
    output_file = skill_dir / "SKILL.md"

    if output_file.exists() and not force:
        console.print(
            f"[yellow]⚠ {output_file.relative_to(repo)} already exists. "
            "Use --force to overwrite.[/yellow]"
        )
        raise SystemExit(1)

    template = _read_review_template()
    enrichment_block = build_enrichment_block(repo)
    repo_namespace = sanitize_skill_namespace(repo.name)

    def _substitute(text: str) -> str:
        return (
            text.replace("{{REPO_SPECIFIC_CHECKS}}", enrichment_block)
            .replace("{{BASE_BRANCH}}", base_branch)
            .replace("{{REPO}}", repo_namespace)
        )

    skill_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(_substitute(template))
    console.print(f"[green]✔ Created {output_file.relative_to(repo)}[/green]")

    # Sub-agents.md uses {{REPO_SPECIFIC_CHECKS}} too (sub-agent 4's
    # Project Conventions block). scaffold_skills writes it with {{REPO}}
    # and {{BASE_BRANCH}} substituted but leaves the enrichment placeholder
    # alone — finalize it here so the parallel-review path doesn't ship the
    # literal token to the model.
    sub_agents_file = skill_dir / "sub-agents.md"
    if sub_agents_file.exists():
        sub_agents_file.write_text(_substitute(sub_agents_file.read_text()))

    return output_file
