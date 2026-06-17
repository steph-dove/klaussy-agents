"""Shared writers used by the non-Claude backends."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from klausify.agents.base import CapabilityProfile, SkillPayload
from klausify.agents.render import adapt_aux, render_skill_md

console = Console()


def write_skills(
    repo: Path,
    profile: CapabilityProfile,
    payloads: list[SkillPayload],
    *,
    force: bool = False,
) -> list[Path]:
    """Write every skill (adapted for `profile`) into the agent's skills root."""
    repo = repo.resolve()
    skills_dir = repo / profile.skills_root
    created: list[Path] = []

    for payload in payloads:
        skill_dir = skills_dir / payload.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        files = {"SKILL.md": render_skill_md(payload, profile)}
        for name, content in payload.aux_files.items():
            files[name] = adapt_aux(content, profile)

        for filename, content in files.items():
            target = skill_dir / filename
            if target.exists() and target.read_text() == content and not force:
                continue
            target.write_text(content)
            created.append(target)

    if created:
        console.print(
            f"[green]✔ [{profile.label}] wrote {len(created)} skill file(s) "
            f"under {profile.skills_root}/[/green]"
        )
    else:
        console.print(f"[dim][{profile.label}] skills already up to date.[/dim]")
    return created
