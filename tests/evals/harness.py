"""Shared harness for opt-in agent-skill evals.

The skills are LLM-driven, so their behavior can't be a plain unit test. These
evals run a skill's *actual shipped prompt spec* against fixtures via a live
model and assert properties of the output (no AI tells, conventional-commit
shape, a planted bug gets flagged, length budgets, ...).

They are opt-in and never run in normal CI: every eval is gated on
`requires_eval_env`, which skips unless `KLAUSSY_RUN_EVALS=1` is set and the
`claude` CLI is installed. The model is driven through `claude -p` (headless),
so it uses Claude Code's own auth, no `ANTHROPIC_API_KEY` is needed. Run with:

    KLAUSSY_RUN_EVALS=1 uv run --with pytest python -m pytest tests/evals -v

Override the model with `KLAUSSY_EVAL_MODEL` (default: claude-sonnet-4-6).

What these are and aren't: this is a *prompt eval*. The context a skill would
normally gather with tools (a diff, a file, git log) is fed in directly, and we
check the model's output against the spec. It does not exercise the full agentic
loop (tool calls, plan mode, multi-turn) — that's a deliberate scope limit so
the evals stay cheap and CI-safe. For multi-step skills it's closer to a smoke
test of the spec's intent than a full behavioral eval, and the files say so.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from importlib import resources

import pytest

from klaussy.agents.render import permission_target_markdown
from klaussy.forge import FORGE_GITHUB, forge_tokens
from klaussy.skills import (  # noqa: F401 (HUMANIZE_BLOCK re-exported)
    _CLAUDE_PERMISSION_SYNTAX,
    _CLAUDE_PERMISSIONS_FILE,
    BASE_RESOLUTION_BLOCK,
    HUMANIZE_BLOCK,
    SKILL_TEMPLATE_ROOT,
    humanize_pointer,
    render_tokens,
)

DEFAULT_MODEL = "claude-sonnet-4-6"

# Single gate: opt-in flag set AND the claude CLI installed. No API key, the CLI
# carries Claude Code's auth.
requires_eval_env = pytest.mark.skipif(
    os.environ.get("KLAUSSY_RUN_EVALS") != "1" or shutil.which("claude") is None,
    reason="opt-in eval: set KLAUSSY_RUN_EVALS=1 (uses the claude CLI's auth)",
)

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_DYNAMIC_SHELL = re.compile(r"```!\n.*?\n```", re.DOTALL)


def load_skill_body(
    skill: str,
    *,
    repo: str = "myrepo",
    base_branch: str = "main",
    forge: str = FORGE_GITHUB,
    filename: str = "SKILL.md",
) -> str:
    """Return the substituted SKILL.md body for `skill` (or one of its aux files).

    Frontmatter and ```! dynamic-shell blocks are stripped: the eval supplies the
    context those blocks would gather (the diff, git log) directly in the user
    message, so the model isn't told to run commands it can't.

    Every token the scaffolders substitute has to be substituted here too, or a
    literal `{{FORGE}}` reaches the model as text.
    """
    text = (
        resources.files("klaussy")
        .joinpath(f"{SKILL_TEMPLATE_ROOT}/{skill}/{filename}.tmpl")
        .read_text()
    )
    text = render_tokens(
        text,
        {
            "REPO": repo,
            "BASE_BRANCH": base_branch,
            "HUMANIZE": humanize_pointer(repo),
            "HUMANIZE_RULES": HUMANIZE_BLOCK,
            "BASE_RESOLUTION": render_tokens(BASE_RESOLUTION_BLOCK, {"BASE_BRANCH": base_branch}),
            "REPO_SPECIFIC_CHECKS": "",
            **forge_tokens(forge),
            "PERMISSIONS_TARGET": permission_target_markdown(
                "Claude Code", _CLAUDE_PERMISSIONS_FILE, _CLAUDE_PERMISSION_SYNTAX
            ),
        },
    )
    text = _FRONTMATTER.sub("", text, count=1)
    text = _DYNAMIC_SHELL.sub("", text)
    return text.strip()


# Disallowing every action tool forces a single-shot text answer: the CLI is
# agentic, and without this a multi-step skill spec ("enter plan mode", "read
# CLAUDE.md") sends the model off investigating an empty dir until it times out.
# A prompt eval wants the completion, not the agent loop.
_NO_TOOLS = [
    "Bash",
    "Edit",
    "Write",
    "Read",
    "Glob",
    "Grep",
    "Task",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
    "TodoWrite",
]


def complete(system: str, user: str, *, model: str | None = None, timeout: int = 240) -> str:
    """Single-shot completion via the headless `claude` CLI (Claude Code auth).

    `--system-prompt` replaces the agentic default with the eval spec, and every
    action tool is disallowed, so the model answers in one turn as a plain
    completion. Runs in an empty temp dir for good measure.
    """
    model_ = model or os.environ.get("KLAUSSY_EVAL_MODEL", DEFAULT_MODEL)
    with tempfile.TemporaryDirectory() as workdir:
        proc = subprocess.run(
            [
                "claude",
                "-p",
                user,
                "--system-prompt",
                system,
                "--model",
                model_,
                "--disallowed-tools",
                *_NO_TOOLS,
            ],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[-1000:]}")
    return proc.stdout.strip()


def run_skill(
    skill: str,
    context: str,
    *,
    instruction: str | None = None,
    aux: list[str] | None = None,
    with_skills: list[str] | None = None,
    max_tokens: int = 1024,
    timeout: int = 240,
) -> str:
    """Run `skill`'s spec against `context`, returning the model's final output.

    `aux` names sibling files (e.g. `manual.md`) to append to the spec, as the
    agent would have read them when the skill sent it there. `with_skills` does
    the same for whole sibling skills (e.g. humanize, which prose skills point at
    instead of inlining its rules).

    `max_tokens` is accepted for call-site compatibility but unused: the headless
    CLI controls output length. Raise `timeout` when a long spec asks for a long
    answer — the default is a harness limit, not a failing spec.
    """
    _ = max_tokens
    spec = load_skill_body(skill)
    for other in with_skills or []:
        spec += f"\n\n---\nContents of the `myrepo-{other}` skill:\n\n" + load_skill_body(other)
    for name in aux or []:
        spec += f"\n\n---\nContents of {name}:\n\n" + load_skill_body(skill, filename=name)
    system = (
        spec + "\n\n---\nYou are being run as an eval. The context you would normally"
        " gather with tools is provided below. Produce only the skill's final"
        " output, exactly as the skill specifies, with no preamble."
    )
    user = context if instruction is None else f"{instruction}\n\n{context}"
    return complete(system, user, timeout=timeout)


# --- assertion helpers -------------------------------------------------------

# High-confidence deterministic AI tells. Prose output that contains any of these
# failed the humanization spec. Kept as explicit substrings (not the scrubber's
# idempotence) so the check is obvious and has no whitespace false positives.
AI_TELLS = [
    "—",
    "it's worth noting",
    "i wanted to point out",
    "please note that",
    "hope this helps",
    "let me know if",
    "feel free to",
    "happy to help",
    "could potentially",
    "in order to",
    "certainly,",
    "great question",
]

_CONVENTIONAL = re.compile(r"^(feat|fix|refactor|test|docs|chore|style|perf)(\([^)]+\))?: .+")


def ai_tells_present(text: str) -> list[str]:
    """Return the AI tells found in `text` (case-insensitive); empty list is clean."""
    low = text.lower()
    return [t for t in AI_TELLS if t.lower() in low]


def count_sentences(text: str) -> int:
    """Rough sentence count via terminal punctuation; good enough for a bound."""
    return len([s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()])


def is_conventional_subject(line: str) -> bool:
    """True if `line` is a Conventional Commits subject (type(scope): summary)."""
    return bool(_CONVENTIONAL.match(line.strip()))


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
