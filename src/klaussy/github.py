"""Generate PR template if the repo doesn't already have one."""

from importlib import resources
from pathlib import Path

from rich.console import Console

console = Console()


def scaffold_github(*, repo: Path, force: bool = False) -> Path | None:
    """Create .github/PULL_REQUEST_TEMPLATE.md only if none exists."""
    repo = repo.resolve()

    pr_template_file = repo / ".github" / "PULL_REQUEST_TEMPLATE.md"
    search_dirs = [repo, repo / ".github", repo / "docs"]
    has_existing_template = any(
        (d / "PULL_REQUEST_TEMPLATE.md").exists()
        or (d / "pull_request_template.md").exists()
        or (d / "PULL_REQUEST_TEMPLATE").is_dir()
        for d in search_dirs
    )

    if has_existing_template and not force:
        console.print("[dim]PR template already exists, skipping.[/dim]")
        return None

    templates = resources.files("klaussy").joinpath("templates/github")
    content = templates.joinpath("PULL_REQUEST_TEMPLATE.md").read_text()
    pr_template_file.parent.mkdir(parents=True, exist_ok=True)
    pr_template_file.write_text(content)
    console.print(f"[green]✔ Created {pr_template_file.relative_to(repo)}[/green]")
    return pr_template_file
