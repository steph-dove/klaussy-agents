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
    read_pre_plan_guidance,
)

console = Console()

COMMIT_GUARD = "klaussy_commit_guard.py"
COMMENT_GUARD = "klaussy_comment_guard.py"
DEPENDENCY_GUARD = "klaussy_dependency_guard.py"
READ_GUARD = "klaussy_read_guard.py"
GUIDANCE_GUARD = "klaussy_plan_guidance.py"


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
        resources.files("klaussy").joinpath(f"templates/hooks/multi/{template_name}").read_text()
    )
    content = (
        content.replace('"__KLAUSSY_FORMAT_CMD__"', _python_literal(format_cmd))
        .replace('"__KLAUSSY_LINT_CMD__"', _python_literal(lint_cmd))
        .replace('"__KLAUSSY_COMMENT_CHECK_CMD__"', _python_literal(comment_check_cmd))
    )
    dest.write_text(content)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_guidance_script(repo: Path, relpath: str, dialect: str) -> None:
    """Copy the pre-plan guidance injector, baking in the text + dialect."""
    dest = repo / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = (
        resources.files("klaussy").joinpath("templates/hooks/multi/plan_guidance.py").read_text()
    )
    content = content.replace(
        '"__KLAUSSY_GUIDANCE__"', _python_literal(read_pre_plan_guidance())
    ).replace('"__KLAUSSY_DIALECT__"', _python_literal(dialect))
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
        console.print(f"[yellow]⚠ [{label}] {path.name} exists; use --force.[/yellow]")
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

    def _cmd(name: str) -> str:
        # Gemini runs hook commands from the session cwd (not guaranteed to be
        # the root), so a bare relative path can fail; $GEMINI_PROJECT_DIR
        # expands to the project root (documented in the Gemini CLI hooks guide).
        return f'{py} "$GEMINI_PROJECT_DIR/{hooks_dir}/{name}"'

    before: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
        before.append(
            {
                "matcher": "run_shell_command",
                "hooks": [{"type": "command", "command": _cmd(COMMIT_GUARD), "timeout": 60000}],
            }
        )
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    before.append(
        {
            "matcher": "run_shell_command",
            "hooks": [{"type": "command", "command": _cmd(COMMENT_GUARD), "timeout": 60000}],
        }
    )
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    before.append(
        {
            "matcher": "run_shell_command",
            "hooks": [{"type": "command", "command": _cmd(DEPENDENCY_GUARD), "timeout": 60000}],
        }
    )
    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    read_cmd = {"type": "command", "command": _cmd(READ_GUARD), "timeout": 60000}
    before.append({"matcher": "read_file", "hooks": [read_cmd]})

    settings_path = repo / ".gemini" / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    if "hooks" in settings and not force:
        console.print(f"[yellow]⚠ [{label}] hooks already configured; use --force.[/yellow]")
        return
    # BeforeAgent fires after the prompt, before planning — the earliest point
    # Gemini can inject context (BeforeTool can't). Gemini has no plan tool, so
    # the guidance lands each turn rather than only on plan entry.
    _install_guidance_script(repo, f"{hooks_dir}/{GUIDANCE_GUARD}", "gemini")
    guidance_cmd = {"type": "command", "command": _cmd(GUIDANCE_GUARD), "timeout": 60000}
    settings["hooks"] = {
        "BeforeAgent": [{"hooks": [guidance_cmd]}],
        "BeforeTool": before,
        "AfterTool": [{"matcher": "web_fetch", "hooks": [read_cmd]}],
    }
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    _report(label, bool(fmt or lint or com), read=True, web=True, plan=True)


def cursor_hooks(repo: Path, *, force: bool) -> None:
    """Cursor: beforeShellExecution + beforeReadFile (no web-fetch event)."""
    label = "Cursor"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".cursor/hooks"

    hooks: dict[str, list[dict]] = {}
    # Cursor execs the command path directly; rely on the script's shebang.
    # The relative path is intentional and safe: Cursor runs project hooks
    # (.cursor/hooks.json) from the repo root (documented), so no project-dir
    # prefix is needed — unlike Claude/Gemini/Codex. Do NOT "absolutize" this.
    # failClosed: a crashing/malformed guard blocks the action rather than
    # silently allowing it (the guards are hardened to exit cleanly anyway).
    before_shell: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
        before_shell.append(
            {"command": f"{hooks_dir}/{COMMIT_GUARD}", "type": "command", "failClosed": True}
        )
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    before_shell.append(
        {"command": f"{hooks_dir}/{COMMENT_GUARD}", "type": "command", "failClosed": True}
    )
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    before_shell.append(
        {"command": f"{hooks_dir}/{DEPENDENCY_GUARD}", "type": "command", "failClosed": True}
    )
    hooks["beforeShellExecution"] = before_shell
    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    hooks["beforeReadFile"] = [
        {"command": f"{hooks_dir}/{READ_GUARD}", "type": "command", "failClosed": True}
    ]
    # Cursor's beforeSubmitPrompt is block-only; sessionStart is its sole
    # context-injection event, so the guidance lands once per session. Not
    # failClosed — a guidance hiccup must never wedge the session.
    _install_guidance_script(repo, f"{hooks_dir}/{GUIDANCE_GUARD}", "cursor")
    hooks["sessionStart"] = [{"command": f"{hooks_dir}/{GUIDANCE_GUARD}", "type": "command"}]

    if _write_json(
        repo / ".cursor" / "hooks.json", {"version": 1, "hooks": hooks}, force=force, label=label
    ):
        _report(label, bool(fmt or lint or com), read=True, web=False, plan=True)


def codex_hooks(repo: Path, *, force: bool) -> None:
    """Codex: UserPromptSubmit plan-guidance + PreToolUse commit guard on Bash."""
    label = "Codex CLI"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".codex/hooks"
    py = _hook_python()

    def _cmd(name: str) -> str:
        # Codex has no project-root env var and runs hook commands from the
        # session cwd, so a bare relative path is unsafe; `git rev-parse
        # --show-toplevel` self-resolves the repo root from any subdir
        # (klaussy-scaffolded repos are git repos).
        return f'{py} "$(git rev-parse --show-toplevel)/{hooks_dir}/{name}"'

    # Codex has no plan tool, but reports permission_mode ("plan") on stdin and
    # can inject additionalContext from UserPromptSubmit — so the guidance script
    # self-gates to plan mode. Wired unconditionally (independent of lint/format).
    _install_guidance_script(repo, f"{hooks_dir}/{GUIDANCE_GUARD}", "codex")
    hooks_cfg: dict = {
        "UserPromptSubmit": [
            {
                "hooks": [{"type": "command", "command": _cmd(GUIDANCE_GUARD), "timeout": 60}],
            }
        ]
    }
    bash_hooks: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
        bash_hooks.append({"type": "command", "command": _cmd(COMMIT_GUARD), "timeout": 60})
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    bash_hooks.append({"type": "command", "command": _cmd(COMMENT_GUARD), "timeout": 60})
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    bash_hooks.append({"type": "command", "command": _cmd(DEPENDENCY_GUARD), "timeout": 60})
    hooks_cfg["PreToolUse"] = [{"matcher": "Bash", "hooks": bash_hooks}]

    if _write_json(repo / ".codex" / "hooks.json", {"hooks": hooks_cfg}, force=force, label=label):
        _report(
            label,
            bool(fmt or lint or com),
            read=False,
            web=False,
            plan=True,
            read_note="Codex has no pre-file-read hook event",
        )


def copilot_hooks(repo: Path, *, force: bool) -> None:
    """Copilot: sessionStart plan-guidance + preToolUse (fail-closed) commit guard."""
    label = "GitHub Copilot"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".github/hooks"

    # Copilot command hooks support an OS split: `bash` (Linux/macOS) and
    # `powershell` (Windows). Use both so hooks run regardless of platform.
    # sessionStart is Copilot's only context-injection event (preToolUse and
    # userPromptSubmitted can't inject), so the guidance lands once per session.
    # Wired unconditionally (independent of lint/format).
    # Copilot has no project-root env var, but each hook entry takes a `cwd`
    # field; pin it to "." so the relative bash/powershell commands resolve from
    # the repo root. The OS-split form rules out a `$(...)`/env-var prefix
    # (powershell wouldn't honor bash syntax), so `cwd` is the lever.
    _install_guidance_script(repo, f"{hooks_dir}/{GUIDANCE_GUARD}", "copilot")
    hooks_cfg: dict = {
        "sessionStart": [
            {
                "type": "command",
                "cwd": ".",
                "bash": f"python3 {hooks_dir}/{GUIDANCE_GUARD}",
                "powershell": f"python {hooks_dir}/{GUIDANCE_GUARD}",
                "timeoutSec": 60,
            }
        ]
    }
    pre_tool: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
        pre_tool.append(
            {
                "type": "command",
                "cwd": ".",
                "bash": f"python3 {hooks_dir}/{COMMIT_GUARD}",
                "powershell": f"python {hooks_dir}/{COMMIT_GUARD}",
                "timeoutSec": 60,
            }
        )
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    pre_tool.append(
        {
            "type": "command",
            "cwd": ".",
            "bash": f"python3 {hooks_dir}/{COMMENT_GUARD}",
            "powershell": f"python {hooks_dir}/{COMMENT_GUARD}",
            "timeoutSec": 60,
        }
    )
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    pre_tool.append(
        {
            "type": "command",
            "cwd": ".",
            "bash": f"python3 {hooks_dir}/{DEPENDENCY_GUARD}",
            "powershell": f"python {hooks_dir}/{DEPENDENCY_GUARD}",
            "timeoutSec": 60,
        }
    )
    hooks_cfg["preToolUse"] = pre_tool

    config = {"version": 1, "hooks": hooks_cfg}
    if _write_json(
        repo / ".github" / "hooks" / "klaussy-guards.json", config, force=force, label=label
    ):
        _report(
            label,
            bool(fmt or lint or com),
            read=False,
            web=False,
            plan=True,
            read_note="Copilot preToolUse is fail-closed; read-injection "
            "tool args are unconfirmed, so it's omitted",
        )


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

    def _cmd(name: str) -> str:
        # Antigravity's hook cwd/env contract is UNVERIFIED against primary docs,
        # so we self-resolve the repo root via `git rev-parse --show-toplevel` —
        # safe from any cwd, independent of any env var. See the README caveat
        # (the plugin config path/event names here are also unverified).
        return f'{py} "$(git rev-parse --show-toplevel)/{hooks_dir}/{name}"'

    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")
    read_cmd = {"type": "command", "command": _cmd(READ_GUARD)}
    pre: list[dict] = [{"matcher": "view_file", "hooks": [read_cmd]}]
    run_command_hooks: list[dict] = []
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
        run_command_hooks.append({"type": "command", "command": _cmd(COMMIT_GUARD)})
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    run_command_hooks.append({"type": "command", "command": _cmd(COMMENT_GUARD)})
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    run_command_hooks.append({"type": "command", "command": _cmd(DEPENDENCY_GUARD)})
    pre.append({"matcher": "run_command", "hooks": run_command_hooks})
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


def cline_hooks(repo: Path, *, force: bool) -> None:
    """Install event-named executables under `.clinerules/hooks/`.

    Uses `cline_tool_guard.py` as a shim for `PreToolUse` and `PostToolUse`
    to execute commit, comment, and read guards. Runs plan guidance on
    `UserPromptSubmit`.
    """
    label = "Cline"
    fmt, lint, com = _commit_cmds(repo)
    hooks_dir = ".clinerules/hooks"

    # Shared guards driven by the shim.
    if fmt or lint or com:
        _install_script(
            repo,
            f"{hooks_dir}/{COMMIT_GUARD}",
            "commit_guard.py",
            format_cmd=fmt,
            lint_cmd=lint,
            comment_check_cmd=com,
        )
    _install_script(repo, f"{hooks_dir}/{COMMENT_GUARD}", "comment_guard.py")
    _install_script(repo, f"{hooks_dir}/{DEPENDENCY_GUARD}", "dependency_guard.py")
    _install_script(repo, f"{hooks_dir}/{READ_GUARD}", "read_guard.py")

    # Install the bridge shim under PreToolUse and PostToolUse.
    _install_script(repo, f"{hooks_dir}/PreToolUse", "cline_tool_guard.py")
    _install_script(repo, f"{hooks_dir}/PostToolUse", "cline_tool_guard.py")
    # Plan guidance rides UserPromptSubmit (no plan signal on stdin).
    _install_guidance_script(repo, f"{hooks_dir}/UserPromptSubmit", "cline")

    _report(label, bool(fmt or lint or com), read=True, web=True, plan=True)


def _report(
    label: str,
    commit: bool,
    *,
    read: bool,
    web: bool,
    plan: bool = False,
    read_note: str | None = None,
) -> None:
    parts = []
    if commit:
        parts.append("git-commit")
    parts.append("comment-humanize")
    if read:
        parts.append("read-injection")
    if web:
        parts.append("web-fetch")
    if plan:
        parts.append("plan-guidance")
    wired = ", ".join(parts) if parts else "none"
    console.print(f"[green]✔ [{label}] hooks wired: {wired}[/green]")
    if not commit:
        console.print(f"[dim][{label}] git-commit guard skipped (no lint/format detected).[/dim]")
    if read_note:
        console.print(f"[dim][{label}] {read_note}.[/dim]")
