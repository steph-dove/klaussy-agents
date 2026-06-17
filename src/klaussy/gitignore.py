"""Ensure klaussy outputs are gitignored."""

from pathlib import Path

from rich.console import Console

console = Console()

GITIGNORE_ENTRIES = [
    "# klaussy outputs",
    "pr-description.md",
    "REVIEW_OUTPUT.md",
    "plan.md",
]


def update_gitignore(*, repo: Path) -> None:
    """Add klaussy output files to .gitignore if not already present."""
    repo = repo.resolve()
    gitignore = repo / ".gitignore"

    if gitignore.exists():
        content = gitignore.read_text()
    else:
        content = ""

    lines_to_add: list[str] = []
    for entry in GITIGNORE_ENTRIES:
        if entry not in content:
            lines_to_add.append(entry)

    if not lines_to_add:
        console.print("[dim].gitignore already has klaussy entries, skipping.[/dim]")
        return

    # Add a newline separator if file doesn't end with one
    if content and not content.endswith("\n"):
        content += "\n"

    content += "\n".join(lines_to_add) + "\n"
    gitignore.write_text(content)
    console.print("[green]✔ Updated .gitignore with klaussy entries[/green]")
