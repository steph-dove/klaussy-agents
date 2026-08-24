"""Detect the repo's hosting provider and load the {{FORGE}} adapter block.

Skills need provider-specific commands around an otherwise identical procedure,
so the provider is detected once at scaffold time and one tailored block is
substituted, the same shape as {{HUMANIZE}}. Detection reads `origin` only, so
`unknown` is a first-class outcome whose block tells the agent to ask rather
than guess.
"""

from __future__ import annotations

import subprocess
from importlib import resources
from pathlib import Path

FORGE_GITHUB = "github"
FORGE_GITLAB = "gitlab"
FORGE_BITBUCKET = "bitbucket"
FORGE_UNKNOWN = "unknown"

FORGES = [FORGE_GITHUB, FORGE_GITLAB, FORGE_BITBUCKET, FORGE_UNKNOWN]


def _run_git(repo: Path, *args: str) -> str | None:
    """Return stripped stdout of a git command in repo, or None if it can't run."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _remote_url(repo: Path) -> str | None:
    """Return origin's URL, falling back to whichever remote is configured first."""
    url = _run_git(repo, "remote", "get-url", "origin")
    if url:
        return url
    remotes = _run_git(repo, "remote")
    if not remotes:
        return None
    return _run_git(repo, "remote", "get-url", remotes.splitlines()[0].strip())


def _host(url: str) -> str:
    """Extract the host from a git remote URL, scp-style or full URL."""
    text = url.strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    if "@" in text.split("/", 1)[0]:
        text = text.split("@", 1)[1]
    for separator in ("/", ":"):
        text = text.split(separator, 1)[0]
    return text.lower()


def detect_forge(repo: Path) -> str:
    """Identify the hosting provider from the repo's remote URL.

    Matches the host alone, never the whole URL: a repo named
    `github-actions-demo` hosted elsewhere would otherwise read as GitHub.
    Substring matching catches enterprise hosts (`github.acme.com`); anything
    else is reported as unknown rather than guessed at.
    """
    url = _remote_url(repo)
    if not url:
        return FORGE_UNKNOWN

    host = _host(url)
    if "github" in host:
        return FORGE_GITHUB
    if "gitlab" in host:
        return FORGE_GITLAB
    if "bitbucket" in host or "stash" in host:
        return FORGE_BITBUCKET
    return FORGE_UNKNOWN


_CLIS = {FORGE_GITHUB: "gh", FORGE_GITLAB: "glab"}


def forge_cli(forge: str) -> str | None:
    """Return the CLI a forge is driven with, or None where none exists.

    Bitbucket is driven through REST, and `Bash(curl *)` would grant reach far
    past the forge, so it stays None: that prompt is worth keeping.
    """
    return _CLIS.get(forge)


def detect_forge_cli(repo: Path) -> str | None:
    """Return the CLI for the repo's detected host."""
    return forge_cli(detect_forge(repo))


def forge_block(forge: str) -> str:
    """Return the {{FORGE}} adapter block for a forge name."""
    name = forge if forge in FORGES else FORGE_UNKNOWN
    return resources.files("klaussy").joinpath(f"templates/forge/{name}.md").read_text()


def build_forge_block(repo: Path, forge: str | None = None) -> str:
    """Return the adapter block for repo, or for an explicitly named forge."""
    return forge_block(forge or detect_forge(repo))
