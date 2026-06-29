"""klaussy as a library — a stable, programmatic surface over the same
operations the CLI runs, without Typer or interactive prompts.

Import the namespace and call through it (`from klaussy import toolkit; toolkit.init(…)`).
Everything here is part of the supported public surface; the internal modules
(`klaussy.agents`, `klaussy.skills`, `klaussy.hooks`, …) may move, so prefer
this module. The names here intentionally match those submodules, which is why
the surface is namespaced under `toolkit` rather than re-exported onto the package
root (that would shadow the submodules). Functions never prompt: an unset
`base_branch` is auto-detected (falling back to `main`), and agent selection
accepts a list or "all".
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from klaussy.agents import ALL_AGENTS, BACKENDS, resolve_agents
from klaussy.checklist import generate_checklist
from klaussy.claude_md import run_init
from klaussy.github import scaffold_github
from klaussy.gitignore import update_gitignore
from klaussy.humanize import humanize as _humanize_text
from klaussy.session import scaffold_session
from klaussy.skills import SKILL_NAMES

__all__ = [
    "ALL_AGENTS",
    "SKILL_NAMES",
    "ScaffoldResult",
    "init",
    "skills",
    "settings",
    "hooks",
    "github",
    "checklist",
    "session",
    "humanize",
    "humanize_files",
    "status",
]

# Agent selection passed to library functions: a single key, a list of keys,
# the literal "all", or None (= every supported agent).
Agents = str | Sequence[str] | None
PathLike = str | Path
_Step = tuple[str, Callable[[], object]]


@dataclass
class ScaffoldResult:
    """Outcome of a multi-agent scaffold (`init`/`skills`/`settings`/`hooks`).

    `completed` and `skipped` hold the human-readable step labels; a step is
    "skipped" when the underlying generator bailed (e.g. a file exists and
    `force` is False). `ok` is True when nothing was skipped.
    """

    repo: Path
    agents: list[str]
    completed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.skipped


def _resolve_agents(agents: Agents) -> list[str]:
    if agents is None:
        return list(ALL_AGENTS)
    if isinstance(agents, str):
        if agents.strip().lower() == "all":
            return list(ALL_AGENTS)
        return resolve_agents(agents)
    return resolve_agents(",".join(agents))


def _detect_base_branch(repo: Path) -> str | None:
    """First of dev/develop/main/master that exists in the repo's git, if any."""
    for branch in ("dev", "develop", "main", "master"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            capture_output=True,
            cwd=str(repo),
        )
        if result.returncode == 0:
            return branch
    return None


def _base_branch(repo: Path, base_branch: str | None) -> str:
    return base_branch or _detect_base_branch(repo) or "main"


def _run_steps(repo: Path, agents: list[str], steps: list[_Step]) -> ScaffoldResult:
    result = ScaffoldResult(repo=repo, agents=agents)
    for label, step in steps:
        try:
            step()
            result.completed.append(label)
        except SystemExit:
            # Generators raise SystemExit to abort a single step (e.g. a file
            # exists without force) — mirror the CLI and keep going.
            result.skipped.append(label)
    return result


def init(
    repo: PathLike = ".",
    *,
    agents: Agents = None,
    force: bool = False,
    skip_enrich: bool = False,
    base_branch: str | None = None,
    review_template: PathLike | None = None,
) -> ScaffoldResult:
    """Generate full boilerplate for the selected agents (the `klaussy init` flow).

    Writes CLAUDE.md (the shared conventions source), then each agent's skills,
    conventions file, permissions, and hooks, plus the PR template and
    .gitignore entries.
    """
    repo = Path(repo).resolve()
    selected = _resolve_agents(agents)
    branch = _base_branch(repo, base_branch)
    template = Path(review_template) if review_template else None

    steps: list[_Step] = [
        ("CLAUDE.md", lambda: run_init(repo=repo, force=force, skip_enrich=skip_enrich)),
    ]
    for key in selected:
        steps.extend(
            BACKENDS[key].steps(
                repo, force=force, base_branch=branch, review_template=template
            )
        )
    steps.append(("PR template", lambda: scaffold_github(repo=repo, force=force)))
    steps.append(("shared session", lambda: scaffold_session(repo=repo, force=force)))
    steps.append((".gitignore", lambda: update_gitignore(repo=repo)))
    return _run_steps(repo, selected, steps)


def skills(
    repo: PathLike = ".",
    *,
    agents: Agents = None,
    force: bool = False,
    base_branch: str | None = None,
    review_template: PathLike | None = None,
) -> ScaffoldResult:
    """Scaffold the bundled workflow skills into each selected agent's skills dir."""
    repo = Path(repo).resolve()
    selected = _resolve_agents(agents)
    branch = _base_branch(repo, base_branch)
    template = Path(review_template) if review_template else None
    steps: list[_Step] = [
        (
            f"[{key}] skills",
            lambda key=key: BACKENDS[key].run_skills(
                repo, force=force, base_branch=branch, review_template=template
            ),
        )
        for key in selected
    ]
    return _run_steps(repo, selected, steps)


def settings(
    repo: PathLike = ".", *, agents: Agents = None, force: bool = False
) -> ScaffoldResult:
    """Generate stack-appropriate permissions for each selected agent."""
    repo = Path(repo).resolve()
    selected = _resolve_agents(agents)
    steps: list[_Step] = [
        (f"[{key}] settings", lambda key=key: BACKENDS[key].run_settings(repo, force=force))
        for key in selected
    ]
    return _run_steps(repo, selected, steps)


def hooks(
    repo: PathLike = ".", *, agents: Agents = None, force: bool = False
) -> ScaffoldResult:
    """Scaffold hook configurations (git-commit + read-injection guards)."""
    repo = Path(repo).resolve()
    selected = _resolve_agents(agents)
    steps: list[_Step] = [
        (f"[{key}] hooks", lambda key=key: BACKENDS[key].run_hooks(repo, force=force))
        for key in selected
    ]
    return _run_steps(repo, selected, steps)


def github(repo: PathLike = ".", *, force: bool = False) -> Path | None:
    """Generate the PR template; returns its path, or None if one already exists."""
    return scaffold_github(repo=Path(repo).resolve(), force=force)


def session(repo: PathLike = ".", *, force: bool = False) -> Path:
    """Scaffold the cross-agent shared session-state file; returns its path.

    Writes `.agents/session.json` (live working state, gitignored) and its
    protocol doc. Existing live state is preserved unless `force` is set."""
    return scaffold_session(repo=Path(repo).resolve(), force=force)


def checklist(
    repo: PathLike = ".", *, force: bool = False, base_branch: str | None = None
) -> Path:
    """Regenerate the review skill from CLAUDE.md; returns the written path."""
    repo = Path(repo).resolve()
    return generate_checklist(repo=repo, force=force, base_branch=_base_branch(repo, base_branch))


def humanize(text: str) -> str:
    """Deterministically strip AI tells from a string, preserving code."""
    return _humanize_text(text)


def humanize_files(
    paths: Sequence[PathLike], *, write: bool = False, check: bool = False
) -> dict[str, bool]:
    """Scrub files; returns {path: would_change}. `write` rewrites changed files
    in place (ignored when `check` is set, which never modifies anything)."""
    changed: dict[str, bool] = {}
    for raw in paths:
        path = Path(raw)
        original = path.read_text()
        cleaned = _humanize_text(original)
        would_change = cleaned != original
        changed[str(path)] = would_change
        if write and would_change and not check:
            path.write_text(cleaned)
    return changed


def status(repo: PathLike = ".") -> dict[str, str]:
    """Map each expected klaussy file to "exists" or "missing" for a repo."""
    repo_path = Path(repo).resolve()
    # CLAUDE.md is canonically at the repo root; fall back to the legacy
    # .claude/CLAUDE.md layout from older klaussy versions.
    claude_md_root = repo_path / "CLAUDE.md"
    claude_md_legacy = repo_path / ".claude" / "CLAUDE.md"
    files = {
        "CLAUDE.md": claude_md_root if claude_md_root.exists() else claude_md_legacy,
        ".claude/settings.json": repo_path / ".claude" / "settings.json",
    }
    for skill in SKILL_NAMES:
        skill_dir = f"{repo_path.name}-{skill}"
        files[f".claude/skills/{skill_dir}/SKILL.md"] = (
            repo_path / ".claude" / "skills" / skill_dir / "SKILL.md"
        )
    return {name: ("exists" if path.exists() else "missing") for name, path in files.items()}
