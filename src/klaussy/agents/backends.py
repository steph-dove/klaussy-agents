"""Per-agent backends. Each turns canonical klaussy output into native files.

The Claude backend delegates to the original generators so its output is
unchanged. The other agents share `GenericBackend`: same adapted `SKILL.md`
folders (placed in each agent's own skills dir), an agent-native conventions
file, and a best-effort permissions file. Hooks are Claude-only for now —
every other agent uses a different hook I/O protocol, so the generic backend
prints an honest note rather than emit a guard that won't fire.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from klaussy.agents.base import (
    CapabilityProfile,
    ConventionsDoc,
    build_skill_payloads,
    read_canonical_conventions,
)
from klaussy.agents.emit import write_skills
from klaussy.agents.hooks import (
    antigravity_hooks,
    codex_hooks,
    copilot_hooks,
    cursor_hooks,
    gemini_hooks,
)
from klaussy.checklist import generate_checklist
from klaussy.hooks import read_pre_plan_guidance, scaffold_hooks
from klaussy.settings import SENSITIVE_PATTERNS, _detect_stack, generate_settings

console = Console()

Step = tuple[str, Callable[[], object]]

SECRET_IGNORE_MARKER = "# klaussy: keep secrets out of the agent's reach"


def _write_secret_ignore(repo: Path, relpath: str, label: str) -> None:
    """Write/append klaussy's sensitive-file patterns to an agent ignore file.

    Both `.geminiignore` and `.cursorignore` use `.gitignore` syntax and are the
    native way to keep secrets out of those agents' reach — the equivalent of
    Claude's settings deny rules. Idempotent: appends a marked block only if it
    isn't already present, preserving any user-authored entries.
    """
    path = repo / relpath
    block = "\n".join([SECRET_IGNORE_MARKER, *SENSITIVE_PATTERNS]) + "\n"
    if path.exists():
        existing = path.read_text()
        if SECRET_IGNORE_MARKER in existing:
            return
        sep = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + sep + "\n" + block)
    else:
        path.write_text(block)
    console.print(f"[green]✔ [{label}] wrote {relpath} (secret exclusions)[/green]")


def _shell_prefixes(stack: dict[str, bool]) -> list[str]:
    """Map a detected stack to allowed shell-command prefixes."""
    prefixes = ["git"]
    if stack["python"]:
        prefixes += ["python", "pytest", "ruff", "mypy", "pip", "uv"]
    if stack["node"]:
        prefixes += ["npm", "npx", "node", "yarn", "pnpm"]
    if stack["go"]:
        prefixes += ["go"]
    if stack["rust"]:
        prefixes += ["cargo"]
    if stack["make"]:
        prefixes += ["make"]
    return prefixes


def _inline_rules_markdown(doc: ConventionsDoc) -> str:
    """Render project-wide conventions + path-scoped rules as one markdown doc.

    Used by agents (Gemini, Codex) whose conventions file is a single Markdown
    document and which do not read `.claude/rules/`. Path-scoped rules are
    appended with their globs as headings so the scoping intent survives.
    """
    parts = [doc.project_wide.rstrip()]
    if doc.rules:
        parts.append("\n## Path-scoped rules\n")
        for rule in doc.rules:
            globs = ", ".join(f"`{g}`" for g in rule.globs)
            parts.append(f"### Applies to: {globs}\n\n{rule.body.rstrip()}\n")
    return "\n".join(parts).rstrip() + "\n"


def _rule_base_dir(globs: list[str]) -> str | None:
    """Deepest concrete directory a rule's globs share, or None if ambiguous.

    Gemini and Codex scope conventions by *directory placement* — a nested
    `GEMINI.md` / `AGENTS.md` applies when work touches that subtree. We map a
    rule's glob(s) to the path segments before the first wildcard: `src/api/**/
    *.py` → `src/api`. Returns None when the glob resolves to the repo root
    (`**/*.py`), is a wildcard-free literal (no clear directory), or the rule's
    globs disagree on a base — those keep the inline-in-root fallback.
    """
    bases: set[str] = set()
    for glob in globs:
        parts = glob.split("/")
        kept: list[str] = []
        saw_wildcard = False
        for part in parts:
            if any(ch in part for ch in "*?[]"):
                saw_wildcard = True
                break
            kept.append(part)
        # No wildcard at all → a literal path, not a directory scope: bail.
        if not saw_wildcard or not kept:
            return None
        bases.add("/".join(kept))
    if len(bases) != 1:
        return None
    return next(iter(bases))


def _nested_rule_markdown(rule) -> str:
    """A nested conventions file body for one path-scoped rule."""
    globs = ", ".join(f"`{g}`" for g in rule.globs)
    return f"# Rules for {globs}\n\n{rule.body.rstrip()}\n"


class ClaudeBackend:
    """Delegates to the original generators — output is byte-for-byte unchanged."""

    key = "claude"
    label = "Claude Code"

    def run_skills(self, repo, *, force, base_branch, review_template):
        from klaussy.skills import scaffold_skills

        scaffold_skills(
            repo=repo,
            force=force,
            review_template=review_template,
            base_branch=base_branch,
        )

    def run_settings(self, repo, *, force):
        generate_settings(repo=repo, force=force)

    def run_hooks(self, repo, *, force):
        scaffold_hooks(repo=repo, force=force)

    def steps(
        self,
        repo: Path,
        *,
        force: bool,
        base_branch: str,
        review_template: Path | None,
    ) -> list[Step]:
        from klaussy.skills import scaffold_skills

        return [
            (
                "[claude] skills",
                lambda: scaffold_skills(
                    repo=repo,
                    force=force,
                    review_template=review_template,
                    base_branch=base_branch,
                ),
            ),
            (
                "[claude] review enrichment",
                lambda: generate_checklist(
                    repo=repo, force=True, base_branch=base_branch
                ),
            ),
            ("[claude] settings", lambda: generate_settings(repo=repo, force=force)),
            ("[claude] hooks", lambda: scaffold_hooks(repo=repo, force=force)),
        ]


class GenericBackend:
    """Base for SKILL.md-spec agents that aren't Claude Code."""

    key: str
    label: str
    profile: CapabilityProfile

    def run_skills(self, repo, *, force, base_branch, review_template):
        write_skills(
            repo,
            self.profile,
            build_skill_payloads(
                repo=repo,
                base_branch=base_branch,
                review_template=review_template,
            ),
            force=force,
        )

    def run_settings(self, repo, *, force):
        self.emit_settings(repo, force=force)

    def run_hooks(self, repo, *, force):
        self.emit_hooks(repo, force=force)

    def steps(
        self,
        repo: Path,
        *,
        force: bool,
        base_branch: str,
        review_template: Path | None,
    ) -> list[Step]:
        return [
            (
                f"[{self.key}] conventions",
                lambda: self.emit_conventions(repo, force=force),
            ),
            (
                f"[{self.key}] skills",
                lambda: self.run_skills(
                    repo,
                    force=force,
                    base_branch=base_branch,
                    review_template=review_template,
                ),
            ),
            (
                f"[{self.key}] settings",
                lambda: self.run_settings(repo, force=force),
            ),
            (
                f"[{self.key}] hooks",
                lambda: self.run_hooks(repo, force=force),
            ),
        ]

    # --- overridable per agent ------------------------------------------------

    def emit_conventions(self, repo: Path, *, force: bool) -> None:
        raise NotImplementedError

    def emit_settings(self, repo: Path, *, force: bool) -> None:
        raise NotImplementedError

    def emit_hooks(self, repo: Path, *, force: bool) -> None:
        console.print(
            f"[dim][{self.label}] hooks not ported (different hook protocol) — "
            "skipping. Claude hooks remain available.[/dim]"
        )

    # --- shared helpers -------------------------------------------------------

    def _write(self, path: Path, content: str, *, force: bool, what: str) -> None:
        if path.exists() and not force and path.read_text() == content:
            return
        if path.exists() and not force:
            console.print(
                f"[yellow]⚠ [{self.label}] {path.name} exists; use --force.[/yellow]"
            )
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        console.print(f"[green]✔ [{self.label}] wrote {what}[/green]")

    def _warn_no_conventions(self) -> None:
        console.print(
            f"[yellow]⚠ [{self.label}] no CLAUDE.md found — skipping "
            "conventions. Run with claude selected (or generate CLAUDE.md) "
            "first.[/yellow]"
        )

    def _emit_markdown_conventions(
        self, repo: Path, doc: ConventionsDoc, filename: str, *, force: bool
    ) -> None:
        """Write a root markdown conventions file + native nested scoped files.

        For agents (Gemini `GEMINI.md`, Codex `AGENTS.md`) that scope conventions
        by directory placement, a path-scoped rule whose glob resolves to an
        existing subdirectory is emitted as a nested `<dir>/<filename>` — true
        path scoping that loads only when that subtree is touched, and keeps the
        root file small (Codex caps it at 32 KiB). Rules whose globs don't map to
        a real directory (root-level `**` globs, wildcard-free literals) stay
        inlined in the root file so their intent isn't lost.
        """
        nested: list[tuple[str, object]] = []
        inline = []
        for rule in doc.rules:
            base = _rule_base_dir(rule.globs)
            if base and (repo / base).is_dir():
                nested.append((base, rule))
            else:
                inline.append(rule)
        root = ConventionsDoc(project_wide=doc.project_wide, rules=inline)
        self._write(
            repo / filename,
            _inline_rules_markdown(root),
            force=force,
            what=filename,
        )
        for base, rule in nested:
            self._write(
                repo / base / filename,
                _nested_rule_markdown(rule),
                force=force,
                what=f"{base}/{filename}",
            )


class GeminiBackend(GenericBackend):
    key = "gemini"
    label = "Gemini CLI"
    profile = CapabilityProfile(
        key="gemini",
        label="Gemini CLI",
        skills_root=".gemini/skills",
        dynamic_shell=False,
        subagents=False,
        plan_mode=False,
        keep_allowed_tools=False,
        keep_disable_invocation=False,
    )

    def emit_conventions(self, repo, *, force):
        doc = read_canonical_conventions(repo)
        if doc is None:
            self._warn_no_conventions()
            return
        # Gemini loads GEMINI.md hierarchically: a nested file applies when work
        # touches its directory, so path-scoped rules go to nested GEMINI.md.
        self._emit_markdown_conventions(repo, doc, "GEMINI.md", force=force)

    def emit_settings(self, repo, *, force):
        stack = _detect_stack(repo)
        allowed = [f"run_shell_command({p})" for p in _shell_prefixes(stack)]
        content = (
            json.dumps(
                {
                    "tools": {"allowed": allowed},
                    "general": {"defaultApprovalMode": "default"},
                    # Ensure .geminiignore (and .gitignore) are honored so the
                    # secret patterns below actually exclude those files.
                    "context": {
                        "fileFiltering": {
                            "respectGitIgnore": True,
                            "respectGeminiIgnore": True,
                        }
                    },
                },
                indent=2,
            )
            + "\n"
        )
        self._write(
            repo / ".gemini" / "settings.json",
            content,
            force=force,
            what=".gemini/settings.json",
        )
        _write_secret_ignore(repo, ".geminiignore", self.label)

    def emit_hooks(self, repo, *, force):
        gemini_hooks(repo, force=force)


class CursorBackend(GenericBackend):
    key = "cursor"
    label = "Cursor"
    profile = CapabilityProfile(
        key="cursor",
        label="Cursor",
        skills_root=".cursor/skills",
        dynamic_shell=False,
        subagents=False,
        plan_mode=False,
        keep_allowed_tools=False,
        keep_disable_invocation=False,
    )

    def emit_conventions(self, repo, *, force):
        doc = read_canonical_conventions(repo)
        if doc is None:
            self._warn_no_conventions()
            return
        rules_dir = repo / ".cursor" / "rules"
        # Project-wide conventions as an always-applied rule. `description` is
        # only used for agent-decided rules, so it's omitted when alwaysApply.
        body = doc.project_wide.rstrip() + "\n"
        self._write(
            rules_dir / "conventions.mdc",
            "---\nalwaysApply: true\n---\n\n" + body,
            force=force,
            what=".cursor/rules/conventions.mdc",
        )
        # Path-scoped rules as auto-attached rules keyed by glob.
        for rule in doc.rules:
            globs = ", ".join(rule.globs)
            frontmatter = f"---\nglobs: {globs}\nalwaysApply: false\n---\n\n"
            self._write(
                rules_dir / f"{rule.stem}.mdc",
                frontmatter + rule.body.rstrip() + "\n",
                force=force,
                what=f".cursor/rules/{rule.stem}.mdc",
            )

    def emit_settings(self, repo, *, force):
        stack = _detect_stack(repo)
        content = (
            json.dumps(
                {"terminalAllowlist": _shell_prefixes(stack), "mcpAllowlist": []},
                indent=2,
            )
            + "\n"
        )
        self._write(
            repo / ".cursor" / "permissions.json",
            content,
            force=force,
            what=".cursor/permissions.json",
        )
        # .cursorignore (not .cursorindexingignore) blocks agent reads of secrets.
        _write_secret_ignore(repo, ".cursorignore", self.label)

    def emit_hooks(self, repo, *, force):
        cursor_hooks(repo, force=force)


class CodexBackend(GenericBackend):
    key = "codex"
    label = "Codex CLI"
    profile = CapabilityProfile(
        key="codex",
        label="Codex CLI",
        # Codex reads the cross-tool neutral skills path, not .codex/skills.
        skills_root=".agents/skills",
        dynamic_shell=False,
        subagents=False,
        plan_mode=False,
        # Claude's allowed-tools values use Claude tool syntax (Bash(git diff *));
        # drop them so Codex falls back to its own defaults rather than mis-parse.
        keep_allowed_tools=False,
        keep_disable_invocation=False,
    )

    def emit_conventions(self, repo, *, force):
        doc = read_canonical_conventions(repo)
        if doc is None:
            self._warn_no_conventions()
            return
        # Codex merges AGENTS.md root→cwd: a nested AGENTS.md applies in its
        # subtree, so path-scoped rules go to nested files (also keeps the root
        # under Codex's 32 KiB project_doc budget).
        self._emit_markdown_conventions(repo, doc, "AGENTS.md", force=force)

    def emit_settings(self, repo, *, force):
        # Codex deliberately IGNORES approval_policy/sandbox_mode in a project-
        # local .codex/config.toml (safety) — they're honored only in
        # ~/.codex/config.toml or via CLI flags. So we don't write them as active
        # keys here (they'd be silent no-ops); we emit a commented guide instead.
        # Codex also has no per-command allow-list and no secret-read exclusion.
        content = (
            "# Generated by klaussy. Codex project config (loaded when trusted).\n"
            "#\n"
            "# NOTE: Codex ignores approval_policy and sandbox_mode in a\n"
            "# project-local .codex/config.toml for safety. Set them in your user\n"
            "# config (~/.codex/config.toml) or via CLI flags. Recommended:\n"
            "#   approval_policy = \"on-request\"\n"
            "#   sandbox_mode    = \"workspace-write\"\n"
            "# Or run: codex -a on-request -s workspace-write\n"
        )
        self._write(
            repo / ".codex" / "config.toml",
            content,
            force=force,
            what=".codex/config.toml",
        )
        console.print(
            "[dim][Codex CLI] note: approval_policy/sandbox_mode are ignored in a "
            "project-local config.toml — set them in ~/.codex/config.toml or via "
            "CLI flags. Codex also has no per-command allow-list and no secret-read "
            "exclusion (no .codexignore); keep secrets outside the workspace.[/dim]"
        )

    def emit_hooks(self, repo, *, force):
        codex_hooks(repo, force=force)


class CopilotBackend(GenericBackend):
    key = "copilot"
    label = "GitHub Copilot"
    profile = CapabilityProfile(
        key="copilot",
        label="GitHub Copilot",
        skills_root=".github/skills",
        dynamic_shell=False,
        subagents=False,
        plan_mode=False,
        keep_allowed_tools=False,
        keep_disable_invocation=True,  # Copilot honors disable-model-invocation
    )

    def emit_conventions(self, repo, *, force):
        doc = read_canonical_conventions(repo)
        if doc is None:
            self._warn_no_conventions()
            return
        # Repo-wide instructions: plain Markdown, no frontmatter.
        self._write(
            repo / ".github" / "copilot-instructions.md",
            doc.project_wide.rstrip() + "\n",
            force=force,
            what=".github/copilot-instructions.md",
        )
        # Path-scoped rules: .github/instructions/<stem>.instructions.md with applyTo.
        for rule in doc.rules:
            apply_to = ", ".join(rule.globs)
            frontmatter = f"---\napplyTo: \"{apply_to}\"\n---\n\n"
            self._write(
                repo / ".github" / "instructions" / f"{rule.stem}.instructions.md",
                frontmatter + rule.body.rstrip() + "\n",
                force=force,
                what=f".github/instructions/{rule.stem}.instructions.md",
            )

    def emit_settings(self, repo, *, force):
        console.print(
            "[dim][GitHub Copilot] no committed allow-list file (the CLI gates "
            "tools via flags + ~/.copilot/config.json; the cloud agent via repo "
            "settings). Secret content-exclusion is GitHub repo/org settings only "
            "and doesn't cover the CLI/coding agent. Skipping.[/dim]"
        )

    def emit_hooks(self, repo, *, force):
        copilot_hooks(repo, force=force)


ANTIGRAVITY_PLUGIN = ".gemini/antigravity-cli/plugins/klaussy"


class AntigravityBackend(GenericBackend):
    """Google Antigravity — the Gemini-based agentic IDE + Claude-compatible CLI.

    Antigravity reads the cross-tool `AGENTS.md` standard for project-wide
    conventions. Its CLI loads plugins (`plugin.json` + `hooks.json` + `skills/`
    + `rules/`, mirroring Claude's `.claude/` machinery), so klaussy emits a
    committed `klaussy` plugin under `.gemini/antigravity-cli/plugins/klaussy/`
    carrying the skills, path-scoped glob rules, and the commit/read-injection
    guards. Terminal allow/deny lists are primarily IDE settings with no firmly
    documented committed file, so the permissions output is best-effort.
    """

    key = "antigravity"
    label = "Google Antigravity"
    profile = CapabilityProfile(
        key="antigravity",
        label="Google Antigravity",
        # Skills ship inside the committed Antigravity CLI plugin.
        skills_root=f"{ANTIGRAVITY_PLUGIN}/skills",
        dynamic_shell=False,
        subagents=False,
        plan_mode=False,
        # Claude's allowed-tools use Claude tool syntax (Bash(git diff *)); drop
        # them so Antigravity falls back to its own defaults rather than mis-parse.
        keep_allowed_tools=False,
        keep_disable_invocation=False,
    )

    def emit_conventions(self, repo, *, force):
        doc = read_canonical_conventions(repo)
        if doc is None:
            self._warn_no_conventions()
            return
        # Project-wide conventions: the cross-tool AGENTS.md standard (plain md,
        # read in full). Path-scoped rules go to the plugin's rules/ below, so
        # keep AGENTS.md to the project-wide content only.
        self._write(
            repo / "AGENTS.md",
            doc.project_wide.rstrip() + "\n",
            force=force,
            what="AGENTS.md",
        )
        # Path-scoped rules: plugin rules/<stem>.md with glob activation.
        # Antigravity rule activation (always_on / manual / model_decision / glob)
        # is declared in frontmatter; path-scoped rules map to `trigger: glob`.
        rules_dir = repo / ANTIGRAVITY_PLUGIN / "rules"
        for rule in doc.rules:
            globs = ", ".join(rule.globs)
            frontmatter = f"---\ntrigger: glob\nglobs: {globs}\n---\n\n"
            self._write(
                rules_dir / f"{rule.stem}.md",
                frontmatter + rule.body.rstrip() + "\n",
                force=force,
                what=f"{ANTIGRAVITY_PLUGIN}/rules/{rule.stem}.md",
            )
        # Pre-plan guardrails: Antigravity hooks return only allow/deny (no
        # context injection), so unlike the other agents the guidance can't ride
        # a hook. It lands instead as an always-applied developer-rules file that
        # Antigravity auto-indexes from the workspace root.
        self._write(
            repo / ".antigravityrules",
            read_pre_plan_guidance(),
            force=force,
            what=".antigravityrules",
        )

    def emit_settings(self, repo, *, force):
        # Best-effort: Antigravity's terminal allow/deny lists are primarily IDE
        # settings; the committed path/format isn't firmly documented. Write a
        # plausible workspace allowlist under .agents/ and flag it as best-effort.
        # Real command-gating is enforced by the plugin's hooks.json commit guard.
        stack = _detect_stack(repo)
        content = (
            json.dumps(
                {"terminal": {"allowList": _shell_prefixes(stack), "denyList": []}},
                indent=2,
            )
            + "\n"
        )
        self._write(
            repo / ".agents" / "settings.json",
            content,
            force=force,
            what=".agents/settings.json",
        )
        console.print(
            "[dim][Google Antigravity] note: the .agents/settings.json allow-list "
            "is best-effort (terminal allow/deny lists are primarily IDE settings); "
            "command-gating is really enforced by the plugin's hooks.json commit "
            "guard. No committed secret-read exclusion is documented — keep secrets "
            "out of the workspace.[/dim]"
        )

    def emit_hooks(self, repo, *, force):
        antigravity_hooks(repo, force=force)


BACKENDS: dict[str, ClaudeBackend | GenericBackend] = {
    b.key: b
    for b in (
        ClaudeBackend(),
        GeminiBackend(),
        CursorBackend(),
        CodexBackend(),
        CopilotBackend(),
        AntigravityBackend(),
    )
}
