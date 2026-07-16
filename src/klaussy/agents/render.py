"""Adapt canonical (Claude-flavored) skill content to a target agent.

The goal is fidelity of *intent*, not bytes: a skill must capture the same
request in a form the reading agent can act on. Three Claude-isms need
adaptation, because the skill bodies are written in Claude's syntax:

* ```! dynamic-shell blocks — execute at load time in Claude/Gemini, inert
  elsewhere. Rewritten to explicit "run this command" instructions.
* parallel sub-agent orchestration — the body uses Claude's `Agent`/
  `subagent_type` syntax. Most agents now have their own sub-agent tool
  (Cursor `Task`, Codex `spawn_agent`, Gemini subagents, Copilot `task`), so a
  capability banner tells the agent to use its equivalent (or go sequential if
  it has none) rather than asserting the capability is absent.
* plan mode / ExitPlanMode — mapped to "use your plan/approval mode, else
  present your plan and wait for approval" via the same banner.

`.claude/skills/...` path references are rewritten to the agent's own skills
root so cross-file references (e.g. review → sub-agents.md) stay valid.
"""

from __future__ import annotations

import re

from klaussy.agents.base import CapabilityProfile, SkillPayload

_PERMISSIONS_TOKEN = "{{PERMISSIONS_TARGET}}"

_DYNAMIC_BLOCK = re.compile(r"```!\n(.*?)\n```", re.DOTALL)
_SUBAGENT_HINT = re.compile(
    r"sub-?agent|Agent tool|in parallel|subagent_type|launch \d", re.IGNORECASE
)
_PLAN_MODE_HINT = re.compile(r"plan mode|ExitPlanMode", re.IGNORECASE)


def _replace_dynamic_block(match: re.Match[str]) -> str:
    """Turn a ```! fenced block into plain run-this-command instructions."""
    commands = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    if not commands:
        return ""
    if len(commands) == 1:
        return f"Run `{commands[0]}` and use its output."
    bullets = "\n".join(f"- `{c}`" for c in commands)
    return "Run these commands and use their output:\n\n" + bullets


def permission_target_markdown(
    label: str, permissions_file: str | None, permission_syntax: str | None
) -> str:
    """Compose the agent-specific "where your allow-list lives" block.

    Replaces the `{{PERMISSIONS_TARGET}}` sentinel in the grant-permissions
    skill so each agent's copy is scoped to its own permission file and rule
    shape instead of carrying a table of all agents. When `permissions_file`
    is None the agent has no committed per-command allow-list; `permission_syntax`
    then explains what it gates on instead.
    """
    header = "## Where your allow-list lives\n"
    if permissions_file:
        return (
            f"{header}\n"
            f"You're running **{label}**. Write permissions to {permissions_file}, "
            f"using {permission_syntax}. Prefer the local, git-ignored file so one "
            "developer's convenience list isn't committed onto the team; only write "
            "a shared, committed file if the user asks to apply it team-wide. The "
            "rule examples below use Claude Code's `Bash(...)` / `Edit(...)` form, "
            "translate them to your file's shape."
        )
    return (
        f"{header}\n"
        f"You're running **{label}**. {permission_syntax} So this skill's "
        "file-writing steps don't apply as written; tell the user that plainly, and "
        "where the agent has an equivalent control (an ignore file, a settings UI, a "
        "test/lint gate) point them at it instead of writing an allow-list."
    )


def _apply_permission_target(text: str, profile: CapabilityProfile) -> str:
    """Resolve the `{{PERMISSIONS_TARGET}}` sentinel for this profile, if present."""
    if _PERMISSIONS_TOKEN not in text:
        return text
    block = permission_target_markdown(
        profile.label, profile.permissions_file, profile.permission_syntax
    )
    return text.replace(_PERMISSIONS_TOKEN, block)


def _capability_banner(body: str, profile: CapabilityProfile) -> str:
    """A short translation note, only for capabilities the body actually uses.

    Added when the skill references parallel sub-agents / plan mode using
    Claude's native syntax and the target isn't Claude — so the agent knows to
    map that syntax to its own equivalent (or go sequential). Simple skills
    (commit, pr, explain) reference neither, so they get no banner.
    """
    notes: list[str] = []
    if not profile.subagents and _SUBAGENT_HINT.search(body):
        if profile.subagent_mechanism:
            notes.append(
                "This skill orchestrates parallel sub-agents using Claude's "
                "`Agent` tool / `subagent_type` syntax. On "
                f"{profile.label}, {profile.subagent_mechanism}"
            )
        else:
            notes.append(
                "This skill orchestrates parallel sub-agents using Claude's `Agent` "
                "tool / `subagent_type` syntax. Most coding agents now have their own "
                "parallel sub-agent or task mechanism (e.g. Cursor's `Task`, Codex's "
                "`spawn_agent`, Gemini subagents, Copilot's `task`) — use yours and "
                "translate the wording. If it truly has none, apply each lens or angle "
                "yourself, sequentially, and combine the findings."
            )
    if not profile.plan_mode and _PLAN_MODE_HINT.search(body):
        if profile.plan_mechanism:
            notes.append(
                f'Where it references "plan mode" or `ExitPlanMode`, {profile.plan_mechanism}'
            )
        else:
            notes.append(
                'Where it references "plan mode" or `ExitPlanMode`, use your agent\'s '
                "own plan/approval mode if it has one; otherwise present your plan and "
                "wait for explicit approval before editing any files."
            )
    if not notes:
        return ""
    body = "\n".join(f"- {n}" for n in notes)
    return (
        f"> **Adapted for {profile.label}.**\n>\n"
        + "\n".join(f"> {line}" for line in body.splitlines())
        + "\n\n"
    )


def adapt_body(body: str, profile: CapabilityProfile) -> str:
    """Adapt a canonical skill body for the given target profile."""
    text = body
    if not profile.dynamic_shell:
        text = _DYNAMIC_BLOCK.sub(_replace_dynamic_block, text)
    if profile.skills_root != ".claude/skills":
        text = text.replace(".claude/skills/", f"{profile.skills_root}/")
    text = _apply_permission_target(text, profile)
    # Detect capabilities against the adapted text: a subagent/plan-mode mention
    # that lived inside a stripped ```! block shouldn't trigger a banner.
    return _capability_banner(text, profile) + text


def adapt_aux(content: str, profile: CapabilityProfile) -> str:
    """Adapt an auxiliary skill file (e.g. review's sub-agents.md).

    Aux files carry no frontmatter and rarely contain ```! blocks, but the same
    dynamic-block and path rewrites apply. No capability banner — the banner
    lives on the SKILL.md the agent loads first.
    """
    text = content
    if not profile.dynamic_shell:
        text = _DYNAMIC_BLOCK.sub(_replace_dynamic_block, text)
    if profile.skills_root != ".claude/skills":
        text = text.replace(".claude/skills/", f"{profile.skills_root}/")
    return text


def render_skill_md(payload: SkillPayload, profile: CapabilityProfile) -> str:
    """Render a full SKILL.md (frontmatter + adapted body) for the profile."""
    lines = ["---", f"name: {payload.name}", f"description: {payload.description}"]
    if profile.keep_allowed_tools and payload.allowed_tools:
        lines.append(f"allowed-tools: {payload.allowed_tools}")
    if profile.keep_disable_invocation and payload.disable_invocation:
        lines.append("disable-model-invocation: true")
    lines.append("---")
    frontmatter = "\n".join(lines)
    return f"{frontmatter}\n\n{adapt_body(payload.body, profile)}"
