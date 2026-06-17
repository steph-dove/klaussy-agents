"""Scaffold Claude Code hook configurations."""

import json
import stat
from importlib import resources
from pathlib import Path

from rich.console import Console

console = Console()

GUARD_SCRIPT_NAME = "read_injection_guard.py"
GUARD_RELPATH = f".claude/hooks/{GUARD_SCRIPT_NAME}"
GUARD_COMMAND = f"python3 {GUARD_RELPATH}"

COMMIT_GUARD_SCRIPT_NAME = "git_commit_guard.py"
COMMIT_GUARD_RELPATH = f".claude/hooks/{COMMIT_GUARD_SCRIPT_NAME}"
COMMIT_GUARD_COMMAND = f"python3 {COMMIT_GUARD_RELPATH}"


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
    repo: Path, *, format_cmd: str | None, lint_cmd: str | None
) -> Path:
    """Render the git-commit guard with project-specific commands baked in."""
    dest = repo / COMMIT_GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(f"templates/hooks/{COMMIT_GUARD_SCRIPT_NAME}")
    content = source.read_text()
    content = content.replace('"__KLAUSSY_FORMAT_CMD__"', _python_literal(format_cmd))
    content = content.replace('"__KLAUSSY_LINT_CMD__"', _python_literal(lint_cmd))
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def scaffold_hooks(*, repo: Path, force: bool = False) -> Path:
    """Add hook configurations to .claude/settings.json."""
    repo = repo.resolve()
    settings_file = repo / ".claude" / "settings.json"

    # Load existing settings or start fresh
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    else:
        settings = {}

    if "hooks" in settings and not force:
        console.print(
            "[yellow]⚠ Hooks already configured in settings.json. "
            "Use --force to overwrite.[/yellow]"
        )
        raise SystemExit(1)

    lint_cmd = _detect_lint_command(repo)
    format_cmd = _detect_format_command(repo)

    # Read-injection guard: scan file/URL content for prompt-injection markers
    # before Claude consumes it. PreToolUse blocks malicious local files; the
    # WebFetch hook runs PostToolUse (fetch can't be inspected pre-flight) and
    # surfaces a warning so the model treats the fetched content as untrusted.
    _install_guard_script(repo)
    pretooluse: list[dict] = [
        {
            "matcher": "Read",
            "hooks": [{"type": "command", "command": GUARD_COMMAND}],
        },
    ]
    posttooluse: list[dict] = [
        {
            "matcher": "WebFetch",
            "hooks": [{"type": "command", "command": GUARD_COMMAND}],
        },
    ]

    # Git-commit guard: real Claude Code hook (PreToolUse on Bash) that detects
    # `git commit` invocations and runs the project's format + lint before
    # letting the commit proceed. Replaces the prior bogus "PreCommit" entry
    # (Claude Code has no PreCommit event; that block never fired).
    if format_cmd or lint_cmd:
        _install_commit_guard_script(repo, format_cmd=format_cmd, lint_cmd=lint_cmd)
        pretooluse.append(
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": COMMIT_GUARD_COMMAND}],
            }
        )

    hooks: dict = {"PreToolUse": pretooluse, "PostToolUse": posttooluse}

    settings["hooks"] = hooks
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    console.print(f"[green]✔ Added hooks to {settings_file.relative_to(repo)}[/green]")
    console.print(f"[green]✔ Installed read-injection guard at {GUARD_RELPATH}[/green]")
    if format_cmd or lint_cmd:
        console.print(
            f"[green]✔ Installed git-commit guard at {COMMIT_GUARD_RELPATH}[/green]"
        )
    else:
        console.print(
            "[dim]Skipped git-commit guard (no lint/format commands detected).[/dim]"
        )

    return settings_file
