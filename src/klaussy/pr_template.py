"""Generate the host's pull/merge request template if the repo lacks one.

The body is host-agnostic; only the path differs. GitHub reads
`.github/PULL_REQUEST_TEMPLATE.md`, GitLab reads
`.gitlab/merge_request_templates/`, and Bitbucket is skipped because its
default description is a repo setting, not a tracked file.
"""

from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy.forge import FORGE_BITBUCKET, FORGE_GITLAB, FORGE_UNKNOWN, FORGES, detect_forge

console = Console()

_GITHUB_TARGET = Path(".github") / "PULL_REQUEST_TEMPLATE.md"
_GITLAB_TARGET = Path(".gitlab") / "merge_request_templates" / "Default.md"


def _github_has_template(repo: Path) -> bool:
    search_dirs = [repo, repo / ".github", repo / "docs"]
    return any(
        (d / "PULL_REQUEST_TEMPLATE.md").exists()
        or (d / "pull_request_template.md").exists()
        or (d / "PULL_REQUEST_TEMPLATE").is_dir()
        for d in search_dirs
    )


def _gitlab_has_template(repo: Path) -> bool:
    templates_dir = repo / ".gitlab" / "merge_request_templates"
    return templates_dir.is_dir() and any(templates_dir.glob("*.md"))


def _resolve_host(repo: Path, forge: str | None) -> str:
    """Validate an explicit forge name, or detect one from the repo.

    An unrecognized name fails loudly; falling through to the GitHub branch
    would silently write the wrong path for a typo like `gitlub`.
    """
    if forge is None:
        return detect_forge(repo)
    name = forge.strip().lower()
    if name not in FORGES:
        raise ValueError(f"Unknown forge {forge!r}. Choose one of: {', '.join(FORGES)}.")
    return name


def scaffold_pr_template(
    *, repo: Path, force: bool = False, forge: str | None = None
) -> Path | None:
    """Write the request template where this repo's host reads it.

    Returns the path written, or None when one already exists or the host has
    nowhere to put it.
    """
    repo = repo.resolve()
    host = _resolve_host(repo, forge)

    if host == FORGE_BITBUCKET:
        console.print(
            "[dim]Bitbucket has no repo-file request template "
            "(its default description is a repo setting), skipping.[/dim]"
        )
        return None

    if host == FORGE_GITLAB:
        target, exists = _GITLAB_TARGET, _gitlab_has_template(repo)
    else:
        # Undetected hosts fall back to the GitHub layout: a stray markdown file
        # is inert if the guess is wrong, and skipping would deny a template to
        # every repo scaffolded before its remote exists.
        if host == FORGE_UNKNOWN:
            console.print(
                "[dim]Host not identified from origin, using the GitHub layout. "
                "Pass --forge to choose.[/dim]"
            )
        target, exists = _GITHUB_TARGET, _github_has_template(repo)

    if exists and not force:
        console.print("[dim]Request template already exists, skipping.[/dim]")
        return None

    content = (
        resources.files("klaussy").joinpath("templates/github/PULL_REQUEST_TEMPLATE.md").read_text()
    )
    template_file = repo / target
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text(content)
    console.print(f"[green]✔ Created {template_file.relative_to(repo)}[/green]")
    return template_file
