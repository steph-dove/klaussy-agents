"""MCP server for klaussy — exposes klaussy subcommands as tools."""

import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

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
    comma-separated list from: claude, gemini, cursor, codex, copilot (or "all").
    Defaults to all agents. Also writes the PR template and .gitignore entries.
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
def klaussy_settings(
    repo: str = ".", force: bool = False, agents: str = "all"
) -> str:
    """Generate stack-appropriate permissions for each selected agent.

    `agents` is a comma-separated list from claude, gemini, cursor, codex,
    copilot (or "all"); defaults to all. Copilot has no per-repo permission
    model and is skipped.
    """
    args = ["settings", "--repo", repo]
    if force:
        args.append("--force")
    if agents.strip().lower() == "all":
        args.append("--all")
    else:
        args.extend(["--agents", agents])
    return _run_klaussy(*args, cwd=repo)


SKILL_NAMES = [
    "review", "plan", "debug", "implement", "refactor",
    "test", "fix", "pr", "commit", "explain", "new-worktree",
]


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
    copilot (or "all"); defaults to all. See src/klaussy/skills.py for the set.
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
    repo_path = Path(repo).resolve()
    # CLAUDE.md is canonically at the repo root (per Claude Code memory
    # docs); fall back to .claude/CLAUDE.md for repos still on the legacy
    # layout from older klaussy versions.
    claude_md_root = repo_path / "CLAUDE.md"
    claude_md_legacy = repo_path / ".claude" / "CLAUDE.md"
    files = {
        "CLAUDE.md": (
            claude_md_root if claude_md_root.exists() else claude_md_legacy
        ),
        ".claude/settings.json": repo_path / ".claude" / "settings.json",
    }
    for skill in SKILL_NAMES:
        skill_dir = f"{repo_path.name}-{skill}"
        rel_path = f".claude/skills/{skill_dir}/SKILL.md"
        files[rel_path] = repo_path / ".claude" / "skills" / skill_dir / "SKILL.md"

    status = {}
    for name, path in files.items():
        status[name] = "exists" if path.exists() else "missing"

    return json.dumps(status, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
