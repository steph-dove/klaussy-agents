"""Per-agent hook emission: install guard scripts + write native hook configs.

Every supported agent has a hooks mechanism, but the config file, event names,
matchers, timeout units, and command form all differ. The *guard scripts* are
shared (cross-agent, dialect-tolerant — see templates/hooks/multi/), so this
module's job is placement + wiring. Coverage isn't uniform: only Gemini and
Cursor expose a pre-file-read event, only Gemini exposes a post-web-fetch event,
and Codex/Copilot only gate shell/tool execution. We wire what each protocol
genuinely supports and log the gaps rather than emit hooks that never fire.
"""

from __future__ import annotations

import json
import stat
import sys
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy.hooks import (
    _detect_comment_check_command,
    _detect_format_command,
    _detect_lint_command,
)

console = Console()

COMMIT_GUARD = "klaussy_commit_guard.py"
READ_GUARD = "klaussy_read_guard.py"


def _hook_python() -> str:
    """Python interpreter token for hook commands on the scaffolding OS.

    python.org Windows installs expose `python`, not `python3`; macOS/Linux
    reliably have `python3`. Agents that run a shell-string hook command (Gemini,
    Codex) get the right token for the OS klaussy runs on. Mixed-OS teams: see
    the README cross-platform note. Copilot uses an explicit bash/powershell
    split, and Cursor execs the script via its shebang, so neither needs this.
    """
    return "python" if sys.platform == "win32" else "python3"


def _python_literal(value: str | None) -> str:
    return repr(value) if value is not None else "None"


def _install_script(
    repo: Path,
    relpath: str,
    template_name: str,
    *,
    format_cmd: str | None = None,
    lint_cmd: str | None = None,
    comment_check_cmd: str | None = None,
) -> None:
    """Copy a guard template into the repo, baking in commands, and chmod +x."""
    dest = repo / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = (
        resources.files("klaussy")
        .joinpath(f"templates/hooks/multi/{template_name}")
        .read_text()
    )
    content = (
        content.replace('"__KLAUSSY_FORMAT_CMD__"', _python_literal(format_cmd))
        .replace('"__KLAUSSY_LINT_CMD__"', _python_literal(lint_cmd))
        .replace(
            '"__KLAUSSY_COMMENT_CHECK_CMD__"', _python_literal(comment_check_cmd)
        )
    )
    dest.write_text(content)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _commit_cmds(repo: Path) -> tuple[str | None, str | None, str | None]:
    return (
        _detect_format_command(repo),
        _detect_lint_command(repo),
        _detect_comment_check_command(repo),
    )


def _write_json(path: Path, data: dict, *, force: bool, label: str) -> bool:
    if path.exists() and not force:
        console.print(
            f"[yellow]⚠ [{label}] {path.name} exists; use --force.[/yellow]"
        )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def gemini_hooks(repo: Path, *, force: bool) -> None:
    """Gemini: BeforeTool (shell + read) and AfterTool (web_fetch)."""
    label = "Gemini CLI"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".gemini/hooks"

    py = _hook_python()
    before: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo, f"{hooks_dir}/{COMMIT_GUARD}", "commit_guard.py",
            format_cmd=fmt, lint_cmd=lint, comment_check_cmd=com,
        )
        before.append({
            "matcher": "run_shell_command",
            "hooks": [{"type": "command",
                       "command": f"{py} {hooks_dir}/{COMMIT_GUARD}",
                       "timeout": 60000}],
        })
    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    read_cmd = {"type": "command", "command": f"{py} {hooks_dir}/{READ_GUARD}",
                "timeout": 60000}
    before.append({"matcher": "read_file", "hooks": [read_cmd]})

    settings_path = repo / ".gemini" / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    if "hooks" in settings and not force:
        console.print(f"[yellow]⚠ [{label}] hooks already configured; use --force.[/yellow]")
        return
    settings["hooks"] = {
        "BeforeTool": before,
        "AfterTool": [{"matcher": "web_fetch", "hooks": [read_cmd]}],
    }
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    _report(label, bool(fmt or lint or com), read=True, web=True)


def cursor_hooks(repo: Path, *, force: bool) -> None:
    """Cursor: beforeShellExecution + beforeReadFile (no web-fetch event)."""
    label = "Cursor"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".cursor/hooks"

    hooks: dict[str, list[dict]] = {}
    if fmt or lint or com:
        _install_script(
            repo, f"{hooks_dir}/{COMMIT_GUARD}", "commit_guard.py",
            format_cmd=fmt, lint_cmd=lint, comment_check_cmd=com,
        )
        # Cursor execs the command path directly; rely on the script's shebang.
        # failClosed: a crashing/malformed guard blocks the action rather than
        # silently allowing it (the guards are hardened to exit cleanly anyway).
        hooks["beforeShellExecution"] = [
            {"command": f"{hooks_dir}/{COMMIT_GUARD}", "type": "command",
             "failClosed": True}
        ]
    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    hooks["beforeReadFile"] = [
        {"command": f"{hooks_dir}/{READ_GUARD}", "type": "command",
         "failClosed": True}
    ]

    if _write_json(repo / ".cursor" / "hooks.json", {"version": 1, "hooks": hooks},
                   force=force, label=label):
        _report(label, bool(fmt or lint or com), read=True, web=False)


def codex_hooks(repo: Path, *, force: bool) -> None:
    """Codex: PreToolUse on Bash only — no pre-read or web-fetch hook surface."""
    label = "Codex CLI"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".codex/hooks"

    if not (fmt or lint or com):
        console.print(
            f"[dim][{label}] no lint/format command detected — no hooks to wire.[/dim]"
        )
        return
    _install_script(
        repo, f"{hooks_dir}/{COMMIT_GUARD}", "commit_guard.py",
        format_cmd=fmt, lint_cmd=lint, comment_check_cmd=com,
    )
    config = {
        "hooks": {
            "PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command",
                           "command": f"{_hook_python()} {hooks_dir}/{COMMIT_GUARD}",
                           "timeout": 60}],
            }]
        }
    }
    if _write_json(repo / ".codex" / "hooks.json", config, force=force, label=label):
        _report(label, True, read=False, web=False,
                read_note="Codex has no pre-file-read hook event")


def copilot_hooks(repo: Path, *, force: bool) -> None:
    """Copilot: preToolUse (fail-closed) — wire only the defensive commit guard."""
    label = "GitHub Copilot"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".github/hooks"

    if not (fmt or lint or com):
        console.print(
            f"[dim][{label}] no lint/format command detected — no hooks to wire.[/dim]"
        )
        return
    _install_script(
        repo, f"{hooks_dir}/{COMMIT_GUARD}", "commit_guard.py",
        format_cmd=fmt, lint_cmd=lint, comment_check_cmd=com,
    )
    # Copilot command hooks support an OS split: `bash` (Linux/macOS) and
    # `powershell` (Windows). Use both so the guard runs regardless of platform.
    config = {
        "version": 1,
        "hooks": {
            "preToolUse": [{
                "type": "command",
                "bash": f"python3 {hooks_dir}/{COMMIT_GUARD}",
                "powershell": f"python {hooks_dir}/{COMMIT_GUARD}",
                "timeoutSec": 60,
            }]
        },
    }
    if _write_json(repo / ".github" / "hooks" / "klaussy-guards.json", config,
                   force=force, label=label):
        _report(label, True, read=False, web=False,
                read_note="Copilot preToolUse is fail-closed; read-injection "
                          "tool args are unconfirmed, so it's omitted")


def antigravity_hooks(repo: Path, *, force: bool) -> None:
    """Antigravity CLI plugin hooks.

    The Antigravity CLI loads plugins from `~/.gemini/antigravity-cli/plugins/`;
    klaussy emits a committed `klaussy` plugin in-repo (import or symlink it into
    that dir). Antigravity uses Claude-style EVENT names (`PreToolUse`/
    `PostToolUse`) but Gemini/Antigravity-native TOOL names — the shell tool is
    `run_command`, file read is `view_file`, web fetch is `read_url_content`
    (NOT Claude's `Bash`/`Read`/`WebFetch`, which don't exist here, so a
    Claude-style matcher would silently never fire). Events are grouped under a
    named key (the plugin name), the form Antigravity merges into
    `~/.gemini/config/hooks.json` — not Claude's top-level `"hooks"`.

    Caveat: this fixes which tools the guards MATCH. Whether the guard scripts
    BLOCK correctly under Antigravity's hook I/O (it reads `toolCall.args.*` on
    stdin and may expect a JSON `{"decision":"deny"}` on stdout rather than the
    `exit 2` other agents honor) is not yet verified — see the README note.
    """
    label = "Google Antigravity"
    fmt, lint, com = _commit_cmds(repo)
    plugin = ".gemini/antigravity-cli/plugins/klaussy"
    hooks_dir = f"{plugin}/hooks"
    py = _hook_python()

    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    read_cmd = {"type": "command", "command": f"{py} {hooks_dir}/{READ_GUARD}"}
    pre: list[dict] = [{"matcher": "view_file", "hooks": [read_cmd]}]
    if fmt or lint or com:
        _install_script(
            repo, f"{hooks_dir}/{COMMIT_GUARD}", "commit_guard.py",
            format_cmd=fmt, lint_cmd=lint, comment_check_cmd=com,
        )
        pre.append({
            "matcher": "run_command",
            "hooks": [{"type": "command",
                       "command": f"{py} {hooks_dir}/{COMMIT_GUARD}"}],
        })
    config = {
        "klaussy": {
            "PreToolUse": pre,
            "PostToolUse": [{"matcher": "read_url_content", "hooks": [read_cmd]}],
        }
    }
    # Required marker file so the Antigravity CLI recognizes the plugin.
    _write_json(
        repo / plugin / "plugin.json",
        {
            "name": "klaussy",
            "version": "0.1.0",
            "description": "klaussy guards, skills, and rules for Antigravity",
        },
        force=force,
        label=label,
    )
    if _write_json(repo / plugin / "hooks.json", config, force=force, label=label):
        _report(label, bool(fmt or lint or com), read=True, web=True)


def _report(
    label: str,
    commit: bool,
    *,
    read: bool,
    web: bool,
    read_note: str | None = None,
) -> None:
    parts = []
    if commit:
        parts.append("git-commit")
    if read:
        parts.append("read-injection")
    if web:
        parts.append("web-fetch")
    wired = ", ".join(parts) if parts else "none"
    console.print(f"[green]✔ [{label}] hooks wired: {wired}[/green]")
    if not commit:
        console.print(
            f"[dim][{label}] git-commit guard skipped (no lint/format detected).[/dim]"
        )
    if read_note:
        console.print(f"[dim][{label}] {read_note}.[/dim]")
