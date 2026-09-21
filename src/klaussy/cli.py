"""CLI entry point for klaussy."""

import dataclasses
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console

from klaussy import __version__
from klaussy import restack as restack_mod
from klaussy import split_carve as carve_mod
from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.checklist import generate_checklist
from klaussy.claude_md import run_init
from klaussy.comment_lint import analyze as analyze_comments
from klaussy.comment_lint import changed_lines
from klaussy.gitignore import update_gitignore
from klaussy.humanize import humanize as humanize_text
from klaussy.import_lint import scan_paths as scan_imports
from klaussy.pr_template import scaffold_pr_template
from klaussy.repo import git_root, resolve_repo
from klaussy.review_prep import prepare_review, render_dict, render_markdown
from klaussy.secret_scan import scan_paths as scan_secrets
from klaussy.skills import HUMANIZE_BLOCK
from klaussy.split_prep import prepare_split
from klaussy.split_prep import render_dict as render_split_dict
from klaussy.split_prep import render_markdown as render_split_markdown

app = typer.Typer(name="klaussy", help="Multi-agent repo boilerplate generator.")
console = Console()

_AGENTS_HELP = (
    "Comma-separated target agents to scaffold "
    f"({', '.join(ALL_AGENTS)}). Defaults to all; pass a subset to narrow."
)


_HERE_OPT = typer.Option(
    False,
    "--here",
    help="Scaffold this directory itself, not the repository root it sits in.",
)


def _resolve_repo(path: Path, here: bool = False) -> Path:
    """The repo root for `path`, refusing a home directory that isn't a repo.

    `--here` keeps the given directory, for a subproject inside a larger repo.
    """
    root = path.resolve() if here else resolve_repo(path)
    if root == Path.home() and git_root(root) is None:
        console.print(
            f"[red]✗ {root} is your home directory, not a repository. Run klaussy "
            "from inside the repo you want to scaffold, or pass --repo <path>.[/red]"
        )
        raise typer.Exit(1)
    if root != path.resolve():
        console.print(f"[dim]Using the repository root: {root}[/dim]")
    return root


def _select_agents(agents: str | None, all_agents: bool) -> list[str]:
    """Resolve --agents/--all into a validated list, exiting cleanly on error."""
    try:
        return resolve_agents(agents, all_agents=all_agents)
    except ValueError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(1) from exc


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
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
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
        None,
        "--review-template",
        help="Path to a custom review prompt to use instead of the default.",
    ),
    base_branch: str | None = typer.Option(
        None,
        "--base-branch",
        "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(False, "--all", help="Scaffold every supported agent."),
    here: bool = _HERE_OPT,
) -> None:
    """Generate repo boilerplate for one or more AI coding agents."""
    repo = _resolve_repo(repo, here)
    selected = _select_agents(agents, all_agents)

    if base_branch is None:
        base_branch = _prompt_base_branch(repo)

    console.print(f"[bold]Target agents:[/bold] {', '.join(selected)}")

    # CLAUDE.md is the shared conventions source: klaussy-repo-conventions discovers the
    # repo's rules once, then each non-Claude backend converts them into its own
    # native conventions file. Always generated, even if claude isn't selected.
    steps: list[tuple[str, Callable[[], object]]] = [
        (
            "CLAUDE.md (conventions source)",
            lambda: run_init(repo=repo, force=force, skip_enrich=skip_enrich),
        ),
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
    steps.append(("PR template", lambda: scaffold_pr_template(repo=repo, force=force)))
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
        None,
        "--base-branch",
        "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
    review_template: Path | None = typer.Option(
        None,
        "--review-template",
        help="Custom review prompt to enrich instead of the default (as given to init).",
    ),
    here: bool = _HERE_OPT,
) -> None:
    """Generate a repo-tailored review command from CLAUDE.md."""
    repo = _resolve_repo(repo, here)
    if base_branch is None:
        base_branch = _prompt_base_branch(repo)
    generate_checklist(
        repo=repo, force=force, base_branch=base_branch, review_template=review_template
    )


@app.command()
def skills(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    review_template: Path | None = typer.Option(
        None,
        "--review-template",
        help="Path to a custom review skill body to use instead of the default.",
    ),
    base_branch: str | None = typer.Option(
        None,
        "--base-branch",
        "-b",
        help="Base branch for diffs (e.g. dev, main). Prompts if not provided.",
    ),
    agents: str | None = typer.Option(None, "--agents", help=_AGENTS_HELP),
    all_agents: bool = typer.Option(
        False, "--all", help="Scaffold skills for every supported agent."
    ),
    here: bool = _HERE_OPT,
) -> None:
    """Scaffold each bundled skill into every selected agent's skills directory."""
    repo = _resolve_repo(repo, here)
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
    here: bool = _HERE_OPT,
) -> None:
    """Generate stack-appropriate permissions for every selected agent."""
    repo = _resolve_repo(repo, here)
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
    here: bool = _HERE_OPT,
) -> None:
    """Scaffold hook configurations (Claude Code; other agents print a note)."""
    repo = _resolve_repo(repo, here)
    selected = _select_agents(agents, all_agents)
    for key in selected:
        try:
            BACKENDS[key].run_hooks(repo, force=force)
        except SystemExit:
            console.print(f"[yellow]⚠ Skipped {key} hooks[/yellow]")


@app.command("pr-template")
def pr_template(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    forge: str | None = typer.Option(
        None,
        "--forge",
        help="Host to target (github/gitlab/bitbucket). Detected from origin if omitted.",
    ),
) -> None:
    """Generate the pull/merge request template where this repo's host reads it."""
    try:
        scaffold_pr_template(repo=_resolve_repo(repo), force=force, forge=forge)
    except ValueError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def uninstall(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    all_: bool = typer.Option(
        False,
        "--all",
        help="Also remove CLAUDE.md / GEMINI.md / AGENTS.md / CONVENTIONS.md.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed and stop."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Remove klaussy's scaffolding from this repo.

    Conventions docs are kept by default: they get hand-edited, and klaussy has
    no way to tell your prose from what it generated. Pass --all to take them.
    """
    from klaussy.uninstall import apply as apply_plan
    from klaussy.uninstall import plan as build_plan

    computed = build_plan(_resolve_repo(repo), include_conventions=all_)

    if computed.is_empty:
        console.print("[dim]Nothing to remove — no klaussy scaffolding found.[/dim]")
        return

    console.print(f"[bold]Would remove {len(computed.removals)} path(s):[/bold]")
    for removal in computed.removals[:20]:
        suffix = "/" if removal.is_dir else ""
        console.print(f"  [red]-[/red] {removal.path}{suffix}  [dim]({removal.reason})[/dim]")
    if len(computed.removals) > 20:
        console.print(f"  [dim]… and {len(computed.removals) - 20} more[/dim]")

    for edit in computed.edits:
        console.print(f"  [yellow]~[/yellow] {edit.path}  [dim]({edit.reason})[/dim]")
    for path, why in computed.kept:
        console.print(f"  [green]keep[/green] {path}  [dim]({why})[/dim]")

    if dry_run:
        console.print("[dim]Dry run — nothing was changed.[/dim]")
        return

    if not yes and not typer.confirm("Remove these?", default=False):
        console.print("[dim]Aborted — nothing was changed.[/dim]")
        raise typer.Exit(1)

    done = apply_plan(computed)
    console.print(f"[green]✔ Removed {len(done.removals)} path(s).[/green]")
    if done.edits:
        console.print(f"[green]✔ Edited {len(done.edits)} shared file(s).[/green]")
    console.print(
        "[dim]klaussy itself is still installed; "
        "`pipx uninstall klaussy-agents` removes the package.[/dim]"
    )


@app.command(hidden=True)
def github(
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
) -> None:
    """Deprecated: use `klaussy pr-template`."""
    console.print("[yellow]⚠ `klaussy github` is now `klaussy pr-template`.[/yellow]")
    scaffold_pr_template(repo=_resolve_repo(repo), force=force)


@app.command()
def humanize(
    files: list[Path] | None = typer.Argument(
        None, help="Files to humanize. Reads stdin and writes stdout if omitted."
    ),
    write: bool = typer.Option(
        False, "--write", "-w", help="Rewrite files in place instead of printing."
    ),
    check: bool = typer.Option(
        False, "--check", help="Exit 1 if any file would change; don't modify."
    ),
    rules: bool = typer.Option(
        False, "--rules", help="Print the prompt-side humanization rules and exit."
    ),
) -> None:
    """Deterministically scrub the mechanical AI tells from prose, preserving all code.

    A conservative subset only: dashes, a fixed list of filler openers and
    scaffolding phrases, a few hedges. It never cuts, shortens, or restyles
    anything, so it is the backstop for a rewrite and not a humanize pass on its
    own — that is the `<repo>-humanize` skill, which runs this last.

    The canonical scrubber shared with klaussy-desktop. With no files it reads
    stdin and writes the result to stdout — so other tools can pipe through it
    (e.g. `printf '%s' "$comment" | klaussy humanize`).

    `--rules` prints the prompt-side block instead of scrubbing. The scrubber is
    a conservative subset of it, so a tool that builds its own review prompt can
    embed these rules rather than maintaining a copy that drifts.
    """
    if rules:
        sys.stdout.write(HUMANIZE_BLOCK + "\n")
        return

    if not files:
        sys.stdout.write(humanize_text(sys.stdin.read()))
        return

    changed = False
    for path in files:
        original = path.read_text()
        cleaned = humanize_text(original)
        if cleaned != original:
            changed = True
        if check:
            if cleaned != original:
                console.print(f"[yellow]would humanize {path}[/yellow]")
            continue
        if write:
            if cleaned != original:
                path.write_text(cleaned)
                console.print(f"[green]✔ humanized {path}[/green]")
        else:
            sys.stdout.write(cleaned)

    if check and changed:
        raise typer.Exit(1)


@app.command(name="comment-lint")
def comment_lint(
    files: list[Path] = typer.Argument(
        ..., help="Source files to scan for over-long comment blocks."
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Only flag comments overlapping lines changed vs HEAD (used by the precommit guard).",
    ),
) -> None:
    """Flag verbose comments (block-only); exit 1 if any are found.

    The deterministic backstop the precommit guard runs after format/lint to
    catch narration comments ruff can't. It only reports — stripping a flagged
    comment to the bare minimum is left to the author. Unreadable files and
    unsupported languages are skipped silently.

    With --diff, findings are scoped to lines that differ from HEAD, so
    pre-existing comments elsewhere in a changed file don't block the commit.
    """
    findings = []
    for path in files:
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        scope = changed_lines(str(path)) if diff else None
        findings.extend(analyze_comments(str(path), text, scope))

    for finding in findings:
        console.print(finding.render(), soft_wrap=True)
    if findings:
        raise typer.Exit(1)


@app.command(name="import-lint")
def import_lint(
    files: list[Path] = typer.Argument(
        ..., help="Python files to scan for function-local imports."
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Only flag imports on lines changed vs HEAD (used by the precommit guard).",
    ),
) -> None:
    """Flag imports inside a function or class (block-only); exit 1 if any are found.

    Hoisting is left to the author: a `# noqa` on the line marks a local import
    deliberate and is honored. With --diff, findings are scoped to lines that
    differ from HEAD, so a pre-existing local import elsewhere in a changed file
    doesn't block.
    """
    findings = scan_imports([str(f) for f in files], diff=diff)
    for finding in findings:
        console.print(finding.render(), soft_wrap=True)
    if findings:
        raise typer.Exit(1)


@app.command(name="secret-scan")
def secret_scan(
    files: list[Path] = typer.Argument(..., help="Files to scan for hardcoded secrets."),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Only flag secrets on lines changed vs HEAD (used by the commit guard).",
    ),
) -> None:
    """Flag hardcoded secrets on changed lines (block-only); exit 1 if any are found.

    The deterministic secret gate the commit guard runs alongside format/lint. It
    reports `file:line` and the kind of credential; removing it is left to the
    author. With --diff, findings are scoped to lines that differ from HEAD, so a
    pre-existing value elsewhere in a touched file doesn't block the commit.
    """
    findings = scan_secrets([str(f) for f in files], diff=diff)
    for finding in findings:
        console.print(finding.render(), soft_wrap=True)
    if findings:
        raise typer.Exit(1)


@app.command(name="review-prep")
def review_prep(
    base: str | None = typer.Option(
        None, "--base", "-b", help="Base branch/ref. Auto-detected (dev/main/master) if omitted."
    ),
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    as_json: bool = typer.Option(
        False, "--json", help="Emit structured JSON instead of the markdown payload."
    ),
) -> None:
    """Trim a branch diff to the reviewable files before the review skill reads it.

    Drops lockfiles, generated/vendored trees, minified/binary blobs, and pure
    renames, then prints the trimmed diff plus an explicit manifest of what was
    excluded (so nothing is hidden from the reviewer). Designed to be the diff
    source the review skill consumes — fewer tokens in, faster review.
    """
    payload = prepare_review(repo=_resolve_repo(repo), base_branch=base)
    if as_json:
        import json

        sys.stdout.write(json.dumps(render_dict(payload), indent=2) + "\n")
    else:
        sys.stdout.write(render_markdown(payload))


@app.command(name="split-prep")
def split_prep(
    base: str | None = typer.Option(
        None, "--base", "-b", help="Base branch/ref. Auto-detected (dev/main/master) if omitted."
    ),
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
    ref: str = typer.Option("HEAD", "--ref", help="Tip of the work to analyse."),
    as_json: bool = typer.Option(
        False, "--json", help="Emit structured JSON instead of the markdown proposal."
    ),
) -> None:
    """Propose stack layers for a large change, from its import graph.

    Sizes the diff in code lines rather than raw lines, then reads bottom-first
    layers off a topological sort of the imports that stay inside the change.
    Files in an import cycle share a layer; ungraphable languages are listed
    rather than guessed at.
    """
    payload = prepare_split(repo=_resolve_repo(repo), base_branch=base, ref=ref)
    if as_json:
        import json

        sys.stdout.write(json.dumps(render_split_dict(payload), indent=2) + "\n")
    else:
        sys.stdout.write(render_split_markdown(payload))


_CHECK_OPT = typer.Option(
    [],
    "--check",
    help="A build/lint/test command to run on every layer (repeatable). No shell syntax.",
)


@app.command(name="split-carve")
def split_carve(
    plan: Path = typer.Argument(..., help="JSON: {base, tip, layers: [{branch, message, paths}]}"),
    check: list[str] = _CHECK_OPT,
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
) -> None:
    """Carve whole-file layers into a stack of branches, then verify it.

    Each layer branches off the one below and takes its files as they stand at
    the carve source. The top layer must then equal the source byte for byte,
    and every `--check` must pass on every layer. Nothing is pushed.
    """
    try:
        base, tip, layers = carve_mod.load_plan(plan)
        created = carve_mod.carve(repo, base, tip, layers)
        report = carve_mod.verify_stack(repo, base, tip, created, check)
    except carve_mod.CarveError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(1) from exc
    sys.stdout.write(carve_mod.render_report(report))
    if not report.ok:
        raise typer.Exit(1)


@app.command(name="split-verify")
def split_verify(
    tip: str = typer.Option(..., "--tip", help="The carve source commit."),
    layers: str = typer.Option(..., "--layers", help="Layer branches, bottom-up, comma-separated."),
    base: str = typer.Option("main", "--base", "-b", help="Base branch, for the report."),
    check: list[str] = _CHECK_OPT,
    repo: Path = typer.Option(".", "--repo", "-r", help="Path to the repository."),
) -> None:
    """Verify a stack, however it was carved: identity with the source, then checks."""
    names = [x.strip() for x in layers.split(",") if x.strip()]
    try:
        report = carve_mod.verify_stack(repo, base, tip, names, check)
    except carve_mod.CarveError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        raise typer.Exit(1) from exc
    sys.stdout.write(carve_mod.render_report(report))
    if not report.ok:
        raise typer.Exit(1)


restack_app = typer.Typer(
    help="Rebase a stack of dependent branches bottom-up, verify it, and push it."
)
app.add_typer(restack_app, name="restack")

_REPO_OPT = typer.Option(".", "--repo", "-r", help="Path to the repository.")
_BASE_OPT = typer.Option(
    None, "--base", "-b", help="Base branch. Defaults to origin/HEAD, then main."
)


def _restack_fail(exc: Exception) -> None:
    console.print(f"[red]✗ {exc}[/red]")
    raise typer.Exit(1) from exc


def _report_run(repo: Path, state: "restack_mod.RunState") -> None:
    if state.current:
        files = restack_mod.conflicted_files(repo)
        sys.stdout.write(
            f"CONFLICT rebasing {state.current} in: {', '.join(files) or '(see git status)'}\n"
            "Resolve each file, `git add` it, run `git rebase --continue`, then "
            "`klaussy restack run --continue`. To back out: `klaussy restack undo`.\n"
        )
        raise typer.Exit(2)
    landed = f" (skipped landed: {', '.join(state.landed)})" if state.landed else ""
    sys.stdout.write(f"Rebased {', '.join(state.done)}{landed}. Next: klaussy restack verify\n")
    for warning in state.warnings:
        sys.stdout.write(f"WARNING: {warning}\n")
    if state.warnings:
        raise typer.Exit(1)


@restack_app.command("plan")
def restack_plan(
    repo: Path = _REPO_OPT,
    base: str | None = _BASE_OPT,
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Skip `git fetch --all --prune`."),
    as_json: bool = typer.Option(False, "--json", help="Emit structured JSON."),
) -> None:
    """Map the stack from git ancestry and reflogs. Changes nothing."""
    try:
        plan = restack_mod.plan_restack(repo, base, fetch=not no_fetch)
    except restack_mod.RestackError as exc:
        _restack_fail(exc)
    if as_json:
        sys.stdout.write(json.dumps(dataclasses.asdict(plan), indent=2) + "\n")
    else:
        sys.stdout.write(restack_mod.render_plan(plan))


@restack_app.command("run")
def restack_run(
    chain: str | None = typer.Option(
        None, "--chain", help="Confirmed branches, bottom-up, comma-separated."
    ),
    resume: bool = typer.Option(False, "--continue", help="Resume after resolving a conflict."),
    repo: Path = _REPO_OPT,
    base: str | None = _BASE_OPT,
    no_fetch: bool = typer.Option(False, "--no-fetch", help="Skip `git fetch --all --prune`."),
) -> None:
    """Rebase each branch onto its parent's new tip; stops on the first conflict."""
    try:
        if not resume:
            if not chain:
                raise restack_mod.RestackError("pass --chain (from `klaussy restack plan`)")
            branches = [c.strip() for c in chain.split(",") if c.strip()]
            restack_mod.start_run(repo, branches, base, fetch=not no_fetch)
        state = restack_mod.advance(repo)
    except restack_mod.RestackError as exc:
        _restack_fail(exc)
    _report_run(repo, state)


@restack_app.command("verify")
def restack_verify(repo: Path = _REPO_OPT) -> None:
    """Check each branch carries exactly its own commits, unchanged by the move."""
    try:
        checks = restack_mod.verify(repo)
    except restack_mod.RestackError as exc:
        _restack_fail(exc)
    for c in checks:
        status = "ok" if c.ok else "CHECK"
        sys.stdout.write(
            f"{status} {c.branch}: {c.own_commits_before} -> {c.own_commits_after} own commit(s)\n"
        )
        for line in c.changed:
            sys.stdout.write(f"    {line}\n")
    if not all(c.ok for c in checks):
        sys.stdout.write(
            "Commits marked ! changed in the move (expected after a conflict resolution); "
            "review them before pushing.\n"
        )
        raise typer.Exit(1)


@restack_app.command("push")
def restack_push(
    repo: Path = _REPO_OPT,
    remote: str = typer.Option("origin", "--remote", help="Remote to push to."),
) -> None:
    """Force-push each rebased branch bottom-up with a lease; never the base."""
    try:
        results = restack_mod.push(repo, remote)
    except restack_mod.RestackError as exc:
        _restack_fail(exc)
    for name, ok, err in results:
        sys.stdout.write(f"{'pushed' if ok else 'REFUSED'} {name}\n")
        if not ok:
            sys.stdout.write(
                f"    {err}\nThe lease refused it: someone else pushed. Fetch and look before "
                "retrying; never fall back to a bare --force.\n"
            )
            raise typer.Exit(1)


@restack_app.command("undo")
def restack_undo(repo: Path = _REPO_OPT) -> None:
    """Abort the run and put every branch back on its recorded tip."""
    try:
        state = restack_mod.undo(repo)
    except restack_mod.RestackError as exc:
        _restack_fail(exc)
    sys.stdout.write(f"Restored {', '.join(state.old_tip)} to their pre-restack tips.\n")


def main() -> None:
    app()
