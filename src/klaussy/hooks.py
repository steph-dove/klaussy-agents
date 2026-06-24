"""Scaffold Claude Code hook configurations."""

import json
import stat
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy import __version__
from klaussy.skills import _read_version, _write_version

console = Console()

GUARD_SCRIPT_NAME = "read_injection_guard.py"
GUARD_RELPATH = f".claude/hooks/{GUARD_SCRIPT_NAME}"
GUARD_COMMAND = f"python3 {GUARD_RELPATH}"

COMMIT_GUARD_SCRIPT_NAME = "git_commit_guard.py"
COMMIT_GUARD_RELPATH = f".claude/hooks/{COMMIT_GUARD_SCRIPT_NAME}"
COMMIT_GUARD_COMMAND = f"python3 {COMMIT_GUARD_RELPATH}"

PLAN_GUIDANCE_SCRIPT_NAME = "plan_guidance.py"
PLAN_GUIDANCE_RELPATH = f".claude/hooks/{PLAN_GUIDANCE_SCRIPT_NAME}"
PLAN_GUIDANCE_COMMAND = f"python3 {PLAN_GUIDANCE_RELPATH}"


def read_pre_plan_guidance() -> str:
    """The canonical pre-plan guardrails text.

    Single source of truth shared by every agent's plan-guidance hook (baked
    into the installed script) and Antigravity's always-on developer-rules file
    (which has no hook injection surface). Edit `templates/pre_plan_guidance.md`
    to change the guidance everywhere at once.
    """
    source = resources.files("klaussy").joinpath("templates/pre_plan_guidance.md")
    return source.read_text().rstrip() + "\n"


def _detect_lint_command(repo: Path) -> str | None:
    """Detect the project's lint command."""
    if (repo / "pyproject.toml").exists():
        return "ruff check --fix ."
    if (repo / "package.json").exists():
        pkg = json.loads((repo / "package.json").read_text())
        scripts = pkg.get("scripts", {})
        if "lint" in scripts:
            return "npm run lint"
        if "lint:fix" in scripts:
            return "npm run lint:fix"
    if (repo / "Makefile").exists():
        content = (repo / "Makefile").read_text()
        if "lint" in content:
            return "make lint"
    return None


def _detect_comment_check_command(repo: Path) -> str | None:
    """Detect a deterministic commented-out-code check (block-only, no auto-fix).

    Only the objective slice of "comment hygiene" is lintable; verbosity and
    narration are judgment calls handled in the skills, not here. ruff's ERA
    rule flags commented-out code without `--fix`, so it surfaces the lines for
    the author instead of silently deleting intentional commented code.
    """
    if (repo / "pyproject.toml").exists():
        return "ruff check --select ERA ."
    return None


def _detect_format_command(repo: Path) -> str | None:
    """Detect the project's format command."""
    if (repo / "pyproject.toml").exists():
        return "ruff format ."
    if (repo / "package.json").exists():
        pkg = json.loads((repo / "package.json").read_text())
        scripts = pkg.get("scripts", {})
        if "format" in scripts:
            return "npm run format"
        if "prettier" in " ".join(scripts.values()):
            return "npx prettier --write ."
    if (repo / "Makefile").exists():
        content = (repo / "Makefile").read_text()
        if "format" in content:
            return "make format"
    return None


def _install_guard_script(repo: Path) -> Path:
    """Copy the read-injection guard into .claude/hooks/ and mark it executable."""
    dest = repo / GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(f"templates/hooks/{GUARD_SCRIPT_NAME}")
    dest.write_text(source.read_text())
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _python_literal(value: str | None) -> str:
    """Render a value as a Python source-code literal (string or None)."""
    return repr(value) if value is not None else "None"


def _install_commit_guard_script(
    repo: Path,
    *,
    format_cmd: str | None,
    lint_cmd: str | None,
    comment_check_cmd: str | None,
) -> Path:
    """Render the git-commit guard with project-specific commands baked in."""
    dest = repo / COMMIT_GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(f"templates/hooks/{COMMIT_GUARD_SCRIPT_NAME}")
    content = source.read_text()
    content = content.replace('"__KLAUSSY_FORMAT_CMD__"', _python_literal(format_cmd))
    content = content.replace('"__KLAUSSY_LINT_CMD__"', _python_literal(lint_cmd))
    content = content.replace(
        '"__KLAUSSY_COMMENT_CHECK_CMD__"', _python_literal(comment_check_cmd)
    )
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _install_plan_guidance_script(repo: Path, dialect: str) -> Path:
    """Render the pre-plan guidance injector with text + dialect baked in."""
    dest = repo / PLAN_GUIDANCE_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(
        "templates/hooks/multi/plan_guidance.py"
    )
    content = source.read_text()
    content = content.replace(
        '"__KLAUSSY_GUIDANCE__"', _python_literal(read_pre_plan_guidance())
    )
    content = content.replace('"__KLAUSSY_DIALECT__"', _python_literal(dialect))
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _hook_commands(entry: dict) -> set[str]:
    """The command strings a hook entry runs (each klaussy hook runs a unique one)."""
    cmds: set[str] = set()
    for h in entry.get("hooks", []):
        if isinstance(h, dict) and isinstance(h.get("command"), str):
            cmds.add(h["command"])
    return cmds


def _merge_managed_hooks(existing: list, desired: list[dict]) -> tuple[list, int]:
    """Append each desired entry whose command isn't already registered.

    Keyed on the hook command string, so re-running is idempotent and a repo
    that has hooks but is missing only a newer one (e.g. the plan-guidance hook)
    gains it without disturbing the user's own entries. Returns (merged, added).
    """
    existing = [e for e in existing if isinstance(e, dict)]
    present: set[str] = set()
    for e in existing:
        present |= _hook_commands(e)
    merged = list(existing)
    added = 0
    for d in desired:
        if not (_hook_commands(d) & present):
            merged.append(d)
            present |= _hook_commands(d)
            added += 1
    return merged, added


def scaffold_hooks(*, repo: Path, force: bool = False) -> Path:
    """Install klaussy's Claude Code hooks into .claude/settings.json.

    Version-gated like scaffold_skills: a repo already at the current klaussy
    version is left untouched. A version bump (or --force, or a repo with no
    hooks yet) re-runs the install, which is additive — existing/custom entries
    are kept and any klaussy-managed hook the repo is missing (e.g. the pre-plan
    guidance hook added in a later release) is merged in. `force` rewrites the
    klaussy block wholesale.
    """
    repo = repo.resolve()
    settings_file = repo / ".claude" / "settings.json"
    hooks_dir = repo / ".claude" / "hooks"

    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    else:
        settings = {}
    existing_hooks = settings.get("hooks")
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}

    # Version gate (mirrors scaffold_skills): once a repo's hooks are at the
    # current klaussy version AND a hooks block is present, skip — no rewrite, no
    # churn. A version bump re-runs the install so newly-added hooks land
    # automatically; a missing block re-installs even at the same version so the
    # app is never left without the hooks it relies on.
    if not force and existing_hooks and _read_version(hooks_dir) == __version__:
        console.print(f"[dim]Hooks already up to date (v{__version__}), skipping.[/dim]")
        return settings_file

    lint_cmd = _detect_lint_command(repo)
    format_cmd = _detect_format_command(repo)
    comment_check_cmd = _detect_comment_check_command(repo)

    # Managed scripts are generated artifacts — always (re)install them so a repo
    # whose settings.json predates a script (e.g. plan_guidance) still gets it.
    # Read-injection guard scans file/URL content for prompt-injection markers
    # before Claude consumes it (PreToolUse blocks malicious local files; the
    # WebFetch PostToolUse hook surfaces a warning since a fetch can't be inspected
    # pre-flight). Pre-plan guidance fires on EnterPlanMode, the instant plan mode
    # opens, injecting klaussy's guardrails via additionalContext so they shape the
    # plan itself.
    _install_guard_script(repo)
    _install_plan_guidance_script(repo, "claude")
    def _entry(matcher: str, command: str) -> dict:
        return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}

    desired_pre: list[dict] = [
        _entry("Read", GUARD_COMMAND),
        _entry("EnterPlanMode", PLAN_GUIDANCE_COMMAND),
    ]
    desired_post: list[dict] = [_entry("WebFetch", GUARD_COMMAND)]

    # Git-commit guard (PreToolUse on Bash) detects `git commit` invocations and
    # runs the project's format + lint first. Only when the repo has a command to run.
    has_commit_guard = bool(format_cmd or lint_cmd or comment_check_cmd)
    if has_commit_guard:
        _install_commit_guard_script(
            repo,
            format_cmd=format_cmd,
            lint_cmd=lint_cmd,
            comment_check_cmd=comment_check_cmd,
        )
        desired_pre.append(_entry("Bash", COMMIT_GUARD_COMMAND))

    if force or not existing_hooks:
        settings["hooks"] = {"PreToolUse": desired_pre, "PostToolUse": desired_post}
        added = len(desired_pre) + len(desired_post)
    else:
        pre, added_pre = _merge_managed_hooks(existing_hooks.get("PreToolUse", []), desired_pre)
        post, added_post = _merge_managed_hooks(existing_hooks.get("PostToolUse", []), desired_post)
        existing_hooks["PreToolUse"] = pre
        existing_hooks["PostToolUse"] = post
        settings["hooks"] = existing_hooks
        added = added_pre + added_post

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    _write_version(hooks_dir)  # stamp so same-version re-runs skip (see version gate)

    if added:
        console.print(
            f"[green]✔ Added {added} hook(s) to {settings_file.relative_to(repo)}[/green]"
        )
    else:
        console.print(
            f"[dim]Hooks already up to date in {settings_file.relative_to(repo)}.[/dim]"
        )
    console.print(f"[green]✔ Installed read-injection guard at {GUARD_RELPATH}[/green]")
    console.print(
        f"[green]✔ Installed pre-plan guidance hook at {PLAN_GUIDANCE_RELPATH}[/green]"
    )
    if has_commit_guard:
        console.print(
            f"[green]✔ Installed git-commit guard at {COMMIT_GUARD_RELPATH}[/green]"
        )
    else:
        console.print(
            "[dim]Skipped git-commit guard (no lint/format commands detected).[/dim]"
        )

    return settings_file
