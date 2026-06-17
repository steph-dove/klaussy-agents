"""CLI entry point for klaussy."""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from klaussy import __version__
from klaussy.checklist import generate_checklist
from klaussy.claude_md import run_init
from klaussy.github import scaffold_github
from klaussy.gitignore import update_gitignore
from klaussy.hooks import scaffold_hooks
from klaussy.settings import generate_settings
from klaussy.skills import scaffold_skills

app = typer.Typer(name="klaussy", help="Claude Code boilerplate generator.")
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"klaussy {__version__}")
        raise typer.Exit()


def _detect_base_branch(repo: Path) -> str | None:
    """Try to detect the base branch from git."""
    for branch in ["dev", "develop", "main", "master"]:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            capture_output=True,
            cwd=str(repo),
        )
        if result.returncode == 0:
            return branch
    return None


def _prompt_base_branch(repo: Path) -> str:
    """Prompt the user for the base branch."""
    detected = _detect_base_branch(repo)
    if detected:
        default = detected
        prompt_text = f"Base branch (detected: {detected})"
    else:
        default = "main"
        prompt_text = "Base branch"
    return typer.prompt(prompt_text, default=default)


@app.callback()
def _callback(
    version: bool = typer.Option(
        False, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Claude Code boilerplate generator."""


@app.command()
def init(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    skip_enrich: bool = typer.Option(
        False, "--skip-enrich", help="Skip Claude CLI enrichment (faster, no API call)."
    ),
    review_template: Path | None = typer.Option(
        None, "--review-template",
        help="Path to a custom review prompt to use instead of the default.",
    ),
    base_branch: str | None = typer.Option(
        None, "--base-branch", "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
) -> None:
    """Generate all Claude Code boilerplate for a repository."""
    repo = repo.resolve()

    if base_branch is None:
        base_branch = _prompt_base_branch(repo)

    steps: list[tuple[str, callable]] = [
        ("CLAUDE.md", lambda: run_init(repo=repo, force=force, skip_enrich=skip_enrich)),
        # `skills` writes the default review SKILL.md; `review enrichment` then
        # overwrites it with the same template plus per-repo {{REPO_SPECIFIC_CHECKS}}.
        # Reverse the order and the enrichment is silently overwritten.
        ("skills", lambda: scaffold_skills(
            repo=repo, force=force, review_template=review_template, base_branch=base_branch,
        )),
        ("review enrichment", lambda: generate_checklist(
            repo=repo, force=True, base_branch=base_branch,
        )),
        ("settings", lambda: generate_settings(repo=repo, force=force)),
        ("hooks", lambda: scaffold_hooks(repo=repo, force=force)),
        ("PR template", lambda: scaffold_github(repo=repo, force=force)),
        (".gitignore", lambda: update_gitignore(repo=repo)),
    ]

    for name, step in steps:
        try:
            step()
        except SystemExit:
            console.print(f"[yellow]⚠ Skipped {name}[/yellow]")

    console.print("\n[bold green]✔ All boilerplate generated![/bold green]")


@app.command()
def checklist(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    base_branch: str | None = typer.Option(
        None, "--base-branch", "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
) -> None:
    """Generate a repo-tailored review command from CLAUDE.md."""
    repo = repo.resolve()
    if base_branch is None:
        base_branch = _prompt_base_branch(repo)
    generate_checklist(repo=repo, force=force, base_branch=base_branch)


@app.command()
def skills(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    review_template: Path | None = typer.Option(
        None, "--review-template",
        help="Path to a custom review skill body to use instead of the default.",
    ),
    base_branch: str | None = typer.Option(
        None, "--base-branch", "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
) -> None:
    """Scaffold .claude/skills/<repo>-<skill>/ for every bundled klaussy skill."""
    repo = repo.resolve()
    if base_branch is None:
        base_branch = _prompt_base_branch(repo)
    scaffold_skills(
        repo=repo, force=force, review_template=review_template, base_branch=base_branch,
    )


@app.command()
def settings(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
) -> None:
    """Generate .claude/settings.json with stack-appropriate defaults."""
    generate_settings(repo=repo, force=force)


@app.command()
def hooks(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
) -> None:
    """Scaffold Claude Code hook configurations."""
    scaffold_hooks(repo=repo, force=force)


@app.command()
def github(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
) -> None:
    """Generate PR template for the repository."""
    scaffold_github(repo=repo, force=force)


def main() -> None:
    app()
