"""MCP server for klaussy — exposes klaussy subcommands as tools."""

import json
import subprocess

from mcp.server.fastmcp import FastMCP

from klaussy.toolkit import humanize as humanize_text
from klaussy.toolkit import status as klaussy_status_map

mcp = FastMCP("klaussy")


def _run_klaussy(*args: str, cwd: str = ".") -> str:
    """Run a klaussy CLI command and return output."""
    result = subprocess.run(
        ["klaussy", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    if result.returncode != 0:
        output += f"\n[exit code: {result.returncode}]"
    return output.strip()


@mcp.tool()
def klaussy_init(
    repo: str = ".",
    base_branch: str = "main",
    force: bool = False,
    skip_enrich: bool = False,
    agents: str = "all",
) -> str:
    """Generate repo boilerplate for one or more AI coding agents.

    Creates CLAUDE.md (the shared conventions source), then per selected agent:
    skills (review, plan, debug, …) in that agent's native skills directory, a
    native conventions file, and stack-appropriate permissions. `agents` is a
    comma-separated list from: claude, gemini, cursor, codex, copilot,
    antigravity, cline, aider, opencode (or "all"). Defaults to all agents. Also
    writes the PR template and .gitignore entries.
    """
    args = ["init", "--repo", repo, "--base-branch", base_branch]
    if force:
        args.append("--force")
    if skip_enrich:
        args.append("--skip-enrich")
    if agents.strip().lower() == "all":
        args.append("--all")
    else:
        args.extend(["--agents", agents])
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_checklist(
    repo: str = ".",
    base_branch: str = "main",
    force: bool = False,
) -> str:
    """Regenerate the review skill from CLAUDE.md with repo-specific checks."""
    args = ["checklist", "--repo", repo, "--base-branch", base_branch]
    if force:
        args.append("--force")
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_settings(repo: str = ".", force: bool = False, agents: str = "all") -> str:
    """Generate stack-appropriate permissions for each selected agent.

    `agents` is a comma-separated list from claude, gemini, cursor, codex,
    copilot, antigravity, cline, aider, opencode (or "all"); defaults to all.
    Copilot has no per-repo permission model and is skipped; Antigravity's
    permissions are best-effort.
    """
    args = ["settings", "--repo", repo]
    if force:
        args.append("--force")
    if agents.strip().lower() == "all":
        args.append("--all")
    else:
        args.extend(["--agents", agents])
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_skills(
    repo: str = ".",
    base_branch: str = "main",
    force: bool = False,
    agents: str = "all",
) -> str:
    """Scaffold the bundled klaussy skills into each selected agent's skills dir.

    Writes one SKILL.md folder per entry in SKILL_NAMES, adapted to each agent.
    `agents` is a comma-separated list from claude, gemini, cursor, codex,
    copilot, antigravity, cline, aider, opencode (or "all"); defaults to all. See
    src/klaussy/skills.py for the set. Aider has no skills mechanism and is
    skipped with a note.
    """
    args = ["skills", "--repo", repo, "--base-branch", base_branch]
    if force:
        args.append("--force")
    if agents.strip().lower() == "all":
        args.append("--all")
    else:
        args.extend(["--agents", agents])
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_status(repo: str = ".") -> str:
    """Check which klaussy boilerplate files exist in a repository."""
    return json.dumps(klaussy_status_map(repo), indent=2)


@mcp.tool()
def klaussy_hooks(repo: str = ".", force: bool = False, agents: str = "all") -> str:
    """Scaffold hook configurations for each selected agent.

    Installs the git-commit guard (format + lint scoped to the files being
    committed) and the read-injection guard, wired to whatever events each
    agent's protocol exposes. `agents` is a comma-separated list from claude,
    gemini, cursor, codex, copilot, antigravity, cline, aider, opencode (or "all"); defaults to all.
    Aider has no hook mechanism and is skipped (its auto-lint/auto-test config is
    written by the settings step instead).
    """
    args = ["hooks", "--repo", repo]
    if force:
        args.append("--force")
    if agents.strip().lower() == "all":
        args.append("--all")
    else:
        args.extend(["--agents", agents])
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_github(repo: str = ".", force: bool = False) -> str:
    """Generate a PR template for the repository.

    Created only if the repo doesn't already have one (checks the root,
    `.github/`, and `docs/`) unless `force` is set.
    """
    args = ["github", "--repo", repo]
    if force:
        args.append("--force")
    return _run_klaussy(*args, cwd=repo)


@mcp.tool()
def klaussy_humanize(
    text: str | None = None,
    files: str = "",
    repo: str = ".",
    write: bool = False,
    check: bool = False,
) -> str:
    """Deterministically strip AI tells from prose, preserving all code.

    Pass `text` to scrub a string and get the cleaned result back (the common
    case). Or pass `files` (a comma-separated list of paths) to scrub them on
    disk: `write=True` rewrites in place, `check=True` reports whether any file
    would change without modifying it. This is the canonical scrubber shared
    with klaussy-desktop.
    """
    if text is not None:
        return humanize_text(text)
    paths = [f.strip() for f in files.split(",") if f.strip()]
    if not paths:
        return "Provide `text` to scrub a string, or `files` to process on disk."
    args = ["humanize", *paths]
    if write:
        args.append("--write")
    if check:
        args.append("--check")
    return _run_klaussy(*args, cwd=repo)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
