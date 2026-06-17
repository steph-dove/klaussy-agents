"""Adapt canonical (Claude-flavored) skill content to a target agent.

The goal is fidelity of *intent*, not bytes: a skill must capture the same
request in a form the reading agent can act on. Three Claude-isms need
adaptation for agents that lack them:

* ```! dynamic-shell blocks — execute at load time in Claude/Gemini, inert
  elsewhere. Rewritten to explicit "run this command" instructions.
* parallel sub-agent orchestration — softened to "do this sequentially" via a
  capability banner so single-threaded agents still perform the work.
* plan mode / ExitPlanMode — mapped to "present your plan and wait for
  approval" via the same banner.

`.claude/skills/...` path references are rewritten to the agent's own skills
root so cross-file references (e.g. review → sub-agents.md) stay valid.
"""

from __future__ import annotations

import re

from klausify.agents.base import CapabilityProfile, SkillPayload

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


def _capability_banner(body: str, profile: CapabilityProfile) -> str:
    """A short translation note, only for capabilities the body actually uses.

    Added only when the skill references parallel sub-agents / plan mode AND the
    target lacks them — so simple skills (commit, pr, explain) get no banner.
    """
    notes: list[str] = []
    if not profile.subagents and _SUBAGENT_HINT.search(body):
        notes.append(
            "Where this skill says to launch sub-agents in parallel (via a "
            "Task/Agent tool), your environment has no such tool — do that work "
            "yourself, sequentially: apply each described lens or angle to the "
            "material in turn and combine the findings."
        )
    if not profile.plan_mode and _PLAN_MODE_HINT.search(body):
        notes.append(
            "Where it says to \"enter plan mode\" or call `ExitPlanMode`, instead "
            "present your plan to the user and wait for their approval before "
            "editing any files."
        )
    if not notes:
        return ""
    body = "\n".join(f"- {n}" for n in notes)
    return f"> **Adapted for {profile.label}.**\n>\n" + "\n".join(
        f"> {line}" for line in body.splitlines()
    ) + "\n\n"


def adapt_body(body: str, profile: CapabilityProfile) -> str:
    """Adapt a canonical skill body for the given target profile."""
    text = body
    if not profile.dynamic_shell:
        text = _DYNAMIC_BLOCK.sub(_replace_dynamic_block, text)
    if profile.skills_root != ".claude/skills":
        text = text.replace(".claude/skills/", f"{profile.skills_root}/")
    return _capability_banner(body, profile) + text


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
