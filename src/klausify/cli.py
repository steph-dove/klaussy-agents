"""CLI entry point for klausify."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console

from klausify import __version__
from klausify.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klausify.checklist import generate_checklist
from klausify.claude_md import run_init
from klausify.github import scaffold_github
from klausify.gitignore import update_gitignore

app = typer.Typer(name="klausify", help="Multi-agent repo boilerplate generator.")
console = Console()

_AGENTS_HELP = (
    "Comma-separated target agents to scaffold "
    f"({', '.join(ALL_AGENTS)}). Defaults to all; pass a subset to narrow."
)


def _select_agents(agents: str | None, all_agents: bool) -> list[str]:
    """Resolve --agents/--all into a validated list, exiting cleanly on error."""
    try:
        return resolve_agents(agents, all_agents=all_agents)
    except ValueError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(1) from exc


def version_callback(value: bool) -> None:
    if value:
        console.print(f"klausify {__version__}")
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
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(
        False, "--all", help="Scaffold every supported agent."
    ),
) -> None:
    """Generate repo boilerplate for one or more AI coding agents."""
    repo = repo.resolve()
    selected = _select_agents(agents, all_agents)

    if base_branch is None:
        base_branch = _prompt_base_branch(repo)

    console.print(f"[bold]Target agents:[/bold] {', '.join(selected)}")

    # CLAUDE.md is the shared conventions source: conventions-cli discovers the
    # repo's rules once, then each non-Claude backend converts them into its own
    # native conventions file. Always generated, even if claude isn't selected.
    steps: list[tuple[str, Callable[[], object]]] = [
        ("CLAUDE.md (conventions source)",
         lambda: run_init(repo=repo, force=force, skip_enrich=skip_enrich)),
    ]
    for key in selected:
        steps.extend(
            BACKENDS[key].steps(
                repo,
                force=force,
                base_branch=base_branch,
                review_template=review_template,
            )
        )
    steps.append(("PR template", lambda: scaffold_github(repo=repo, force=force)))
    steps.append((".gitignore", lambda: update_gitignore(repo=repo)))

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
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(
        False, "--all", help="Scaffold skills for every supported agent."
    ),
) -> None:
    """Scaffold each bundled skill into every selected agent's skills directory."""
    repo = repo.resolve()
    selected = _select_agents(agents, all_agents)
    if base_branch is None:
        base_branch = _prompt_base_branch(repo)
    for key in selected:
        try:
            BACKENDS[key].run_skills(
                repo,
                force=force,
                base_branch=base_branch,
                review_template=review_template,
            )
        except SystemExit:
            console.print(f"[yellow]⚠ Skipped {key} skills[/yellow]")


@app.command()
def settings(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(
        False, "--all", help="Generate settings for every supported agent."
    ),
) -> None:
    """Generate stack-appropriate permissions for every selected agent."""
    repo = repo.resolve()
    selected = _select_agents(agents, all_agents)
    for key in selected:
        try:
            BACKENDS[key].run_settings(repo, force=force)
        except SystemExit:
            console.print(f"[yellow]⚠ Skipped {key} settings[/yellow]")


@app.command()
def hooks(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(
        False, "--all", help="Scaffold hooks for every supported agent."
    ),
) -> None:
    """Scaffold hook configurations (Claude Code; other agents print a note)."""
    repo = repo.resolve()
    selected = _select_agents(agents, all_agents)
    for key in selected:
        try:
            BACKENDS[key].run_hooks(repo, force=force)
        except SystemExit:
            console.print(f"[yellow]⚠ Skipped {key} hooks[/yellow]")


@app.command()
def github(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
) -> None:
    """Generate PR template for the repository."""
    scaffold_github(repo=repo, force=force)


def main() -> None:
    app()
