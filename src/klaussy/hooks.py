"""Scaffold Claude Code hook configurations."""

import json
import stat
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy import __version__
from klaussy.skills import _read_version, _write_version

console = Console()

# Claude Code runs hook commands in the session's current directory, which is
# NOT guaranteed to be the project root, so a bare relative path can fail to
# resolve; ${CLAUDE_PROJECT_DIR} always expands to the project root. See
# https://code.claude.com/docs/en/hooks.md ("Path Placeholders").
PROJECT_DIR = "${CLAUDE_PROJECT_DIR}"


# Hook commands invoke the guard through klaussy's `klaussy-hook` launcher rather
# than naming a Python interpreter directly. `python3` is absent on a stock
# python.org Windows install and `python` isn't guaranteed on Linux/macOS, and
# Claude's hook config has no per-OS command field to choose between them — so a
# hardcoded token would break whenever the run OS differs from the scaffold OS.
# `klaussy-hook` is a pip console script (on PATH as `klaussy-hook`/`.exe`), so it
# resolves on every OS and runs the guard under klaussy's own interpreter. The
# path is quoted so a project dir with spaces survives ${CLAUDE_PROJECT_DIR}.
def _cmd(relpath: str) -> str:
    return f'klaussy-hook "{PROJECT_DIR}/{relpath}"'


GUARD_SCRIPT_NAME = "read_injection_guard.py"
GUARD_RELPATH = f".claude/hooks/{GUARD_SCRIPT_NAME}"
GUARD_COMMAND = _cmd(GUARD_RELPATH)

COMMIT_GUARD_SCRIPT_NAME = "git_commit_guard.py"
COMMIT_GUARD_RELPATH = f".claude/hooks/{COMMIT_GUARD_SCRIPT_NAME}"
COMMIT_GUARD_COMMAND = _cmd(COMMIT_GUARD_RELPATH)

COMMENT_GUARD_SCRIPT_NAME = "comment_guard.py"
COMMENT_GUARD_RELPATH = f".claude/hooks/{COMMENT_GUARD_SCRIPT_NAME}"
COMMENT_GUARD_COMMAND = _cmd(COMMENT_GUARD_RELPATH)

DEPENDENCY_GUARD_SCRIPT_NAME = "dependency_guard.py"
DEPENDENCY_GUARD_RELPATH = f".claude/hooks/{DEPENDENCY_GUARD_SCRIPT_NAME}"
DEPENDENCY_GUARD_COMMAND = _cmd(DEPENDENCY_GUARD_RELPATH)

PLAN_GUIDANCE_SCRIPT_NAME = "plan_guidance.py"
PLAN_GUIDANCE_RELPATH = f".claude/hooks/{PLAN_GUIDANCE_SCRIPT_NAME}"
PLAN_GUIDANCE_COMMAND = _cmd(PLAN_GUIDANCE_RELPATH)

SELF_REVIEW_GUARD_SCRIPT_NAME = "self_review_guard.py"
SELF_REVIEW_GUARD_RELPATH = f".claude/hooks/{SELF_REVIEW_GUARD_SCRIPT_NAME}"
SELF_REVIEW_GUARD_COMMAND = _cmd(SELF_REVIEW_GUARD_RELPATH)

# Placeholder baked into direct tool commands; the commit guard expands it to
# the staged files at commit time so the gate only judges the change being
# committed. Must match PATHS_TOKEN in the commit-guard templates.
PATHS_PLACEHOLDER = "__KLAUSSY_PATHS__"


def read_pre_plan_guidance() -> str:
    """The canonical pre-plan guardrails text.

    Single source of truth shared by every agent's plan-guidance hook (baked
    into the installed script) and Antigravity's always-on developer-rules file
    (which has no hook injection surface). Edit `templates/pre_plan_guidance.md`
    to change the guidance everywhere at once.
    """
    source = resources.files("klaussy").joinpath("templates/pre_plan_guidance.md")
    return source.read_text().rstrip() + "\n"


def _has_node_tool(pkg: dict, tool: str) -> bool:
    """True if a Node tool is a dependency or named in any package.json script."""
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if tool in deps:
        return True
    return any(tool in script for script in pkg.get("scripts", {}).values())


def _detect_lint_command(repo: Path) -> str | None:
    """Detect the project's lint command, always scoped to the staged files.

    Every command carries the `__KLAUSSY_PATHS__` placeholder, which the commit
    guard expands to the files being committed so the gate judges only the change
    in flight — never the whole tree. We deliberately do NOT fall back to a
    repo-wide `npm run lint` / `npm run lint:fix`: blocking a commit on unrelated
    pre-existing issues (or auto-fixing unrelated files) is the behavior we're
    avoiding. If the linter can't be scoped, the guard skips linting.
    """
    if (repo / "pyproject.toml").exists():
        return f"ruff check --fix {PATHS_PLACEHOLDER}"
    if (repo / "package.json").exists():
        pkg = json.loads((repo / "package.json").read_text())
        if _has_node_tool(pkg, "eslint"):
            return f"npx eslint --fix {PATHS_PLACEHOLDER}"
    return None


def _detect_comment_check_command(repo: Path) -> str | None:
    """Detect a deterministic commented-out-code check (block-only, no auto-fix).

    Covers the commented-out-*code* slice of comment hygiene via ruff's ERA rule,
    which flags without `--fix` so it surfaces the lines instead of silently
    deleting intentional commented code. The other slice — verbose narration
    prose — is caught by the repo-independent `klaussy comment-lint` check the
    commit guard runs alongside this one (see the guard's VERBOSE_COMMENT_CMD).
    """
    if (repo / "pyproject.toml").exists():
        return f"ruff check --select ERA {PATHS_PLACEHOLDER}"
    return None


def _detect_format_command(repo: Path) -> str | None:
    """Detect the project's format command, always scoped to the staged files.

    A formatter runs with `--write`, so an unscoped command (e.g. `npm run
    format`, which is typically `prettier --write .`) would rewrite the entire
    tree on every commit — flooding the diff and blocking the commit if any
    unrelated file fails. We only ever emit a command carrying `__KLAUSSY_PATHS__`
    so the guard touches nothing outside the diff; if the formatter can't be
    scoped, the guard skips formatting rather than run it repo-wide.
    """
    if (repo / "pyproject.toml").exists():
        return f"ruff format {PATHS_PLACEHOLDER}"
    if (repo / "package.json").exists():
        pkg = json.loads((repo / "package.json").read_text())
        if _has_node_tool(pkg, "prettier"):
            # --ignore-unknown so staged files prettier can't parse (e.g. a .py
            # committed alongside JS) are skipped instead of failing the run.
            return f"npx prettier --write --ignore-unknown {PATHS_PLACEHOLDER}"
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


def _install_comment_guard_script(repo: Path) -> Path:
    """Copy the comment-humanizing guard into .claude/hooks/ and mark executable.

    No commands are baked in: it shells out to `klaussy humanize` at run time, so
    a plain copy is enough (unlike the commit guard's format/lint sentinels)."""
    dest = repo / COMMENT_GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(f"templates/hooks/{COMMENT_GUARD_SCRIPT_NAME}")
    dest.write_text(source.read_text())
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _install_dependency_guard_script(repo: Path) -> Path:
    """Copy the dependency gate into .claude/hooks/ and mark executable.

    No commands are baked in — it inspects the install command and blocks on a
    new-dependency add, so the cross-agent `multi/` copy is used verbatim (it
    already reads Claude's `tool_input.command` payload shape)."""
    dest = repo / DEPENDENCY_GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath(
        f"templates/hooks/multi/{DEPENDENCY_GUARD_SCRIPT_NAME}"
    )
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
    content = content.replace('"__KLAUSSY_COMMENT_CHECK_CMD__"', _python_literal(comment_check_cmd))
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def _install_plan_guidance_script(repo: Path, dialect: str) -> Path:
    """Render the pre-plan guidance injector with text + dialect baked in."""
    dest = repo / PLAN_GUIDANCE_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath("templates/hooks/multi/plan_guidance.py")
    content = source.read_text()
    content = content.replace('"__KLAUSSY_GUIDANCE__"', _python_literal(read_pre_plan_guidance()))
    content = content.replace('"__KLAUSSY_DIALECT__"', _python_literal(dialect))
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_self_review_guard_script(repo: Path, dialect: str) -> Path:
    """Render the self-review stop hook with the output dialect baked in."""
    dest = repo / SELF_REVIEW_GUARD_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = resources.files("klaussy").joinpath("templates/hooks/multi/self_review_guard.py")
    content = source.read_text().replace('"__KLAUSSY_DIALECT__"', _python_literal(dialect))
    dest.write_text(content)
    mode = dest.stat().st_mode
    dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest
    return dest


def _hook_commands(entry: dict) -> set[str]:
    """The command strings a hook entry runs (each klaussy hook runs a unique one)."""
    cmds: set[str] = set()
    for h in entry.get("hooks", []):
        if isinstance(h, dict) and isinstance(h.get("command"), str):
            cmds.add(h["command"])
    return cmds


# Every guard klaussy installs. An entry naming one of these is klaussy's to
# manage; anything else in the repo's hooks block is the user's and is left alone.
MANAGED_SCRIPT_NAMES: frozenset[str] = frozenset(
    {
        GUARD_SCRIPT_NAME,
        COMMIT_GUARD_SCRIPT_NAME,
        COMMENT_GUARD_SCRIPT_NAME,
        DEPENDENCY_GUARD_SCRIPT_NAME,
        PLAN_GUIDANCE_SCRIPT_NAME,
        SELF_REVIEW_GUARD_SCRIPT_NAME,
    }
)


def _managed_scripts(entry: dict) -> set[str]:
    """Which klaussy guard scripts an entry invokes, whatever the command form."""
    return {name for cmd in _hook_commands(entry) for name in MANAGED_SCRIPT_NAMES if name in cmd}


def _merge_managed_hooks(existing: list, desired: list[dict]) -> tuple[list, int]:
    """Re-register each desired entry in its current form; keep the user's own.

    Keyed on the guard *script* an entry invokes rather than its full command
    string, because the command form has changed across releases (a bare relative
    path, then `python3 ${CLAUDE_PROJECT_DIR}/...`, now the `klaussy-hook`
    launcher). Keying on the string made every upgrade append a fresh entry and
    leave the old one behind, so a repo accumulated one stale copy of each guard
    per format change — and a stale relative-path copy resolves against the
    session cwd, blocking every matching tool call whenever that isn't the repo
    root. Superseded entries are dropped so an upgrade rewrites in place.

    Returns (merged, added); `added` counts only entries not already registered
    verbatim, so a same-version re-run reports nothing and rewrites identically.
    """
    existing = [e for e in existing if isinstance(e, dict)]
    desired_scripts: set[str] = set()
    for d in desired:
        desired_scripts |= _managed_scripts(d)

    kept: list = []
    superseded: set[str] = set()
    for e in existing:
        if _managed_scripts(e) & desired_scripts:
            superseded |= _hook_commands(e)
        else:
            kept.append(e)

    merged = kept + list(desired)
    added = sum(1 for d in desired if not (_hook_commands(d) & superseded))
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
    # Comment guard rewrites an outgoing `gh` comment through `klaussy humanize`
    # (PreToolUse updatedInput). No project-specific command, so always installed.
    _install_comment_guard_script(repo)
    # Dependency gate blocks a `pip/npm/poetry/… install <pkg>` that adds a new
    # named dependency until the agent confirms it. No project-specific command,
    # so always installed.
    _install_dependency_guard_script(repo)
    # Self-review stop hook: on Stop, if the tree has uncommitted code, ask for one
    # review pass before finishing. Loop-safe (once per session/HEAD); always installed.
    _install_self_review_guard_script(repo, "claude")

    def _entry(matcher: str, command: str) -> dict:
        return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}

    desired_pre: list[dict] = [
        _entry("Read", GUARD_COMMAND),
        _entry("EnterPlanMode", PLAN_GUIDANCE_COMMAND),
        _entry("Bash", COMMENT_GUARD_COMMAND),
        _entry("Bash", DEPENDENCY_GUARD_COMMAND),
    ]
    desired_post: list[dict] = [_entry("WebFetch", GUARD_COMMAND)]
    # Stop takes no matcher (Claude ignores one if present).
    desired_stop: list[dict] = [
        {"hooks": [{"type": "command", "command": SELF_REVIEW_GUARD_COMMAND}]}
    ]

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
        settings["hooks"] = {
            "PreToolUse": desired_pre,
            "PostToolUse": desired_post,
            "Stop": desired_stop,
        }
        added = len(desired_pre) + len(desired_post) + len(desired_stop)
    else:
        pre, added_pre = _merge_managed_hooks(existing_hooks.get("PreToolUse", []), desired_pre)
        post, added_post = _merge_managed_hooks(existing_hooks.get("PostToolUse", []), desired_post)
        stop, added_stop = _merge_managed_hooks(existing_hooks.get("Stop", []), desired_stop)
        existing_hooks["PreToolUse"] = pre
        existing_hooks["PostToolUse"] = post
        existing_hooks["Stop"] = stop
        settings["hooks"] = existing_hooks
        added = added_pre + added_post + added_stop

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    _write_version(hooks_dir)  # stamp so same-version re-runs skip (see version gate)

    if added:
        console.print(
            f"[green]✔ Added {added} hook(s) to {settings_file.relative_to(repo)}[/green]"
        )
    else:
        console.print(f"[dim]Hooks already up to date in {settings_file.relative_to(repo)}.[/dim]")
    console.print(f"[green]✔ Installed read-injection guard at {GUARD_RELPATH}[/green]")
    console.print(f"[green]✔ Installed pre-plan guidance hook at {PLAN_GUIDANCE_RELPATH}[/green]")
    console.print(f"[green]✔ Installed dependency gate at {DEPENDENCY_GUARD_RELPATH}[/green]")
    console.print(
        f"[green]✔ Installed self-review stop hook at {SELF_REVIEW_GUARD_RELPATH}[/green]"
    )
    if has_commit_guard:
        console.print(f"[green]✔ Installed git-commit guard at {COMMIT_GUARD_RELPATH}[/green]")
    else:
        console.print("[dim]Skipped git-commit guard (no lint/format commands detected).[/dim]")

    return settings_file
