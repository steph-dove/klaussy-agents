"""Run the review skill headless on a pull request checkout, with any supported agent.

The GitHub Action and the hosted review App both call this through
`klaussy review --headless`, so the checkout scrub, the command guards and the
agent invocations live in one place.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

from klaussy.skills import sanitize_skill_namespace

REPORT = "REVIEW_OUTPUT.md"
RESUME_PROMPT = f"{REPORT} doesn't exist yet. Finish the review and write it."
CODEX_RESUME_PROMPT = "Finish the review and give the whole report as your final message."
MIN_RESUME_USD = 0.5
MIN_RESUME_SECONDS = 60

# Read from the base branch at any depth; a PR must not write the instructions for its own review.
CONVENTIONS = re.compile(
    r"(^|/)(CLAUDE\.md|CLAUDE\.local\.md|AGENTS\.md|GEMINI\.md)$"
    r"|^\.claude/rules(/|$)|^\.github/copilot-instructions\.md$|^\.github/instructions(/|$)"
)
# Agent config a PR could use to steer, widen or replace its own review.
PR_AGENT_CONFIG = (
    REPORT,
    ".claude/skills",
    ".claude/agents",
    ".claude/commands",
    ".claude/hooks",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".mcp.json",
    ".github/skills",
    ".github/agents",
    ".github/hooks",
    ".copilot",
    ".agents",
    ".codex",
)
# `klaussy init` writes a broad allow-list and hooks that would widen the reviewer's tools.
SCAFFOLD_WIDENERS = (
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/hooks",
    ".github/hooks",
)
GIT_COMMANDS = (
    "diff",
    "log",
    "show",
    "status",
    "merge-base",
    "rev-parse",
    "ls-files",
    "branch",
    "blame",
)
CREDENTIALS = {
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
    "copilot": ("COPILOT_GITHUB_TOKEN",),
    "codex": ("CODEX_API_KEY",),
}
WRITE_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN")


class ReviewRunError(RuntimeError):
    """The checkout couldn't be prepared for a review."""


@dataclass(frozen=True)
class AgentRun:
    returncode: int | None
    stdout: str
    session: str | None = None
    cost_usd: float | None = None
    usage: dict | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class ReviewResult:
    status: str  # ok | no_report | budget | timeout | auth | error
    agent: str
    report_written: bool
    cost_usd: float | None = None
    usage: list[dict] = field(default_factory=list)
    runs: int = 0
    error: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if check and proc.returncode != 0:
        raise ReviewRunError(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}")
    return proc


def _nul_paths(raw: bytes) -> list[str]:
    return [p for p in raw.decode("utf-8", "surrogateescape").split("\0") if p]


def _base_has(repo: Path, base: str, path: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{base}:{path}", check=False).returncode == 0


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _restore_conventions(repo: Path, base: str, *, drop_unknown: bool) -> None:
    on_base = _nul_paths(_git(repo, "ls-tree", "-r", "-z", "--name-only", base).stdout)
    paths = set(p for p in on_base if CONVENTIONS.search(p))
    if drop_unknown:
        head = _nul_paths(_git(repo, "ls-files", "-z").stdout)
        paths |= {p for p in head if CONVENTIONS.search(p)}
    for path in sorted(paths):
        if drop_unknown:
            _remove(repo / path)
        if _base_has(repo, base, path):
            _git(repo, "checkout", "-q", base, "--", path)


def _klaussy(*args: str, repo: Path, env: dict[str, str]) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "klaussy", *args], cwd=repo, env=env, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise ReviewRunError(f"klaussy {args[0]}: {proc.stderr or proc.stdout}")


def prepare_checkout(
    repo: Path, *, base: str, agent: str, diff_out: Path, enrich: bool = False
) -> None:
    """Capture the PR diff, strip the PR's agent config, take conventions from `base` and
    render the review skill for `agent`."""
    # Taken before the reviewer runs, so posting never runs git on a checkout it could touch.
    diff = _git(repo, "diff", "--no-ext-diff", "--no-textconv", f"{base}...HEAD").stdout
    diff_out.write_bytes(diff)

    for top in (".claude", ".claude/rules", ".github", ".github/instructions"):
        if (repo / top).is_symlink():
            (repo / top).unlink()
    nested = [d for d in repo.glob("*/**/.claude") if ".git" not in d.relative_to(repo).parts]
    for path in nested:
        _remove(path)
    for path in PR_AGENT_CONFIG:
        _remove(repo / path)
    _restore_conventions(repo, base, drop_unknown=True)

    env = {**os.environ, "PYTHONSAFEPATH": "1"}
    branch = base.removeprefix("origin/")
    if not (repo / "CLAUDE.md").is_file():
        flags = [] if enrich and agent == "claude" else ["--skip-enrich"]
        _klaussy(
            "init",
            "--repo",
            str(repo),
            "-b",
            branch,
            "--agents",
            agent,
            "--force",
            *flags,
            repo=repo,
            env=env,
        )
    # init can regenerate conventions the base already has; the base's win, and the review
    # skill is built from them afterwards.
    _restore_conventions(repo, base, drop_unknown=False)
    _klaussy(
        "skills",
        "--repo",
        str(repo),
        "-b",
        branch,
        "--agents",
        agent,
        "--force",
        repo=repo,
        env=env,
    )
    for path in SCAFFOLD_WIDENERS:
        _remove(repo / path)


def install_guards(guard_dir: Path) -> dict[str, str]:
    """Write the git and klaussy wrappers and return the env that puts them first on PATH."""
    guard_dir.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if not git:
        raise ReviewRunError("git isn't on PATH")
    klaussy = shutil.which("klaussy") or f'"{sys.executable}" -m klaussy'
    real = {"REAL_GIT": git, "REAL_KLAUSSY": klaussy}
    guards = resources.files("klaussy").joinpath("templates", "review-guards")
    for name in ("git", "klaussy"):
        script = guards.joinpath(name).read_text()
        for placeholder, target in real.items():
            script = script.replace(placeholder, target)
        (guard_dir / name).write_text(script)
        (guard_dir / name).chmod(0o755)
    return {
        "PATH": f"{guard_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "PYTHONSAFEPATH": "1",
    }


def agent_env(agent: str, guard_env: dict[str, str]) -> dict[str, str]:
    """The environment the agent runs in: no token that writes, no other agent's credential."""
    others = {name for key, names in CREDENTIALS.items() if key != agent for name in names}
    env = {k: v for k, v in os.environ.items() if k not in WRITE_TOKENS and k not in others}
    env.update(guard_env)
    if agent == "claude":
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env


def review_prompt(repo_name: str, base: str, *, include_nits: bool, agent: str) -> str:
    skill = f"{sanitize_skill_namespace(repo_name)}-review"
    nits = "Include nits: report Warn and Nit findings too. " if include_nits else ""
    finish = (
        "You can't write files here, so give the whole report, in the skill's format, as your "
        "final message."
        if agent == "codex"
        else f"Finish by writing {REPORT}."
    )
    return (
        f"Use the {skill} skill to review this branch (HEAD) against `{base}`. {nits}"
        f"There is no one to answer questions: make reasonable calls yourself. {finish}"
    )


def _text(stream: str | bytes | None) -> str:
    return stream.decode(errors="replace") if isinstance(stream, bytes) else stream or ""


def _run(
    argv: list[str], *, repo: Path, env: dict[str, str], timeout: float
) -> tuple[int | None, str, str, bool]:
    """(returncode, stdout, stderr, timed_out); a timeout keeps whatever was printed."""
    try:
        proc = subprocess.run(
            argv, cwd=repo, env=env, capture_output=True, text=True, timeout=max(timeout, 1)
        )
    except subprocess.TimeoutExpired as exc:
        return None, _text(exc.stdout), _text(exc.stderr), True
    except OSError as exc:
        return 127, "", f"couldn't start {argv[0]}: {exc}", False
    return proc.returncode, proc.stdout, proc.stderr, False


class Claude:
    key = "claude"
    allowed = (
        "Read",
        "Grep",
        "Glob",
        "Agent",
        "Skill",
        "TodoWrite",
        f"Write({REPORT})",
        f"Edit({REPORT})",
        "Bash(klaussy base:*)",
        "Bash(klaussy review-prep:*)",
        "Bash(python3 -m klaussy base:*)",
        "Bash(python3 -m klaussy review-prep:*)",
        "Bash(python -m klaussy base:*)",
        "Bash(python -m klaussy review-prep:*)",
        "Bash(ls:*)",
        *(f"Bash(git {c}:*)" for c in GIT_COMMANDS),
    )
    denied = ("WebFetch", "WebSearch", "ScheduleWakeup", "Read(//proc/**)")

    def argv(
        self,
        prompt: str,
        *,
        model: str | None,
        budget_usd: float,
        session: str | None,
        work_dir: Path,
        runs: int,
    ) -> list[str]:
        resume = ["--resume", session] if session else []
        return [
            "claude",
            "-p",
            prompt,
            *resume,
            "--model",
            model or "claude-opus-5-5",
            "--max-budget-usd",
            str(budget_usd),
            "--allowedTools",
            *self.allowed,
            "--disallowedTools",
            *self.denied,
            "--settings",
            '{"disableAllHooks": true}',
            "--strict-mcp-config",
            "--output-format",
            "json",
        ]

    def result(
        self,
        returncode: int | None,
        stdout: str,
        timed_out: bool,
        work_dir: Path,
        runs: int,
        session: str | None,
    ) -> AgentRun:
        data: dict = {}
        try:
            data = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
        except (json.JSONDecodeError, IndexError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        cost = data.get("total_cost_usd")
        return AgentRun(
            returncode,
            stdout,
            data.get("session_id"),
            float(cost) if isinstance(cost, (int, float)) else None,
            None,
            timed_out,
        )


class Copilot:
    key = "copilot"
    allowed = (
        f"write({REPORT})",
        "shell(klaussy)",
        "shell(ls)",
        *(f"shell(git {c})" for c in GIT_COMMANDS),
    )

    def __init__(self, max_ai_credits: str | None = None):
        self.max_ai_credits = max_ai_credits

    def argv(
        self,
        prompt: str,
        *,
        model: str | None,
        budget_usd: float,
        session: str | None,
        work_dir: Path,
        runs: int,
    ) -> list[str]:
        start = ["--resume", session] if runs else ["--session-id", session or ""]
        flags = [
            "--deny-tool=url",
            "--disable-builtin-mcps",
            "--no-ask-user",
            "--disallow-temp-dir",
            "--secret-env-vars=COPILOT_GITHUB_TOKEN",
            "--add-dir",
            ".",
            "--no-auto-update",
            "--output-format",
            "json",
            "--usage-output-file",
            str(work_dir / f"copilot-usage-{runs}.json"),
            *(f"--allow-tool={t}" for t in self.allowed),
        ]
        if model:
            flags += ["--model", model]
        if self.max_ai_credits:
            flags += ["--max-ai-credits", self.max_ai_credits]
        return ["copilot", "-p", prompt, *start, *flags]

    def result(
        self,
        returncode: int | None,
        stdout: str,
        timed_out: bool,
        work_dir: Path,
        runs: int,
        session: str | None,
    ) -> AgentRun:
        usage_file = work_dir / f"copilot-usage-{runs}.json"
        usage = None
        if usage_file.is_file():
            try:
                usage = json.loads(usage_file.read_text())
            except json.JSONDecodeError:
                usage = None
        return AgentRun(returncode, stdout, session, None, usage, timed_out)


class Codex:
    key = "codex"

    def argv(
        self,
        prompt: str,
        *,
        model: str | None,
        budget_usd: float,
        session: str | None,
        work_dir: Path,
        runs: int,
    ) -> list[str]:
        head = (
            ["codex", "exec", "resume", session, prompt]
            if runs and session
            else ["codex", "exec", prompt]
        )
        flags = [
            "--sandbox",
            "read-only",
            "--ignore-rules",
            "--ignore-user-config",
            # Commands Codex runs see only core variables, never the API key.
            "-c",
            "shell_environment_policy.inherit=core",
            "--json",
            "--output-last-message",
            str(work_dir / f"codex-last-{runs}.md"),
        ]
        if model:
            flags += ["--model", model]
        return [*head, *flags]

    def result(
        self,
        returncode: int | None,
        stdout: str,
        timed_out: bool,
        work_dir: Path,
        runs: int,
        session: str | None,
    ) -> AgentRun:
        thread, usage = session, None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                thread = event.get("thread_id") or thread
            elif event.get("type") == "turn.completed":
                usage = event.get("usage") or usage
        return AgentRun(returncode, stdout, thread, None, usage, timed_out)


def make_agent(name: str, *, max_ai_credits: str | None = None):
    if name == "claude":
        return Claude()
    if name == "copilot":
        return Copilot(max_ai_credits)
    if name == "codex":
        return Codex()
    raise ValueError(f"agent must be claude, copilot or codex, not {name!r}")


_AUTH = re.compile(r"authentication|unauthori[sz]ed|invalid api key|401|access denied", re.I)


def run_headless_review(
    repo: Path,
    *,
    agent: str,
    base: str,
    repo_name: str,
    work_dir: Path,
    budget_usd: float = 20.0,
    timeout_s: float = 3600,
    model: str | None = None,
    max_ai_credits: str | None = None,
    include_nits: bool = False,
) -> ReviewResult:
    """Run the prepared review once, and resume once with whatever budget and time are left."""
    runner = make_agent(agent, max_ai_credits=max_ai_credits)
    env = agent_env(agent, install_guards(work_dir / "guard"))
    report = repo / REPORT
    deadline = time.monotonic() + timeout_s
    prompt = review_prompt(repo_name, base, include_nits=include_nits, agent=agent)
    session = str(uuid.uuid4()) if agent == "copilot" else None
    spent: float | None = 0.0
    usage: list[dict] = []
    runs = 0
    last: AgentRun | None = None
    log = ""
    skipped = ""
    notes: list[str] = []

    while runs < 2:
        left = budget_usd - (spent or 0.0)
        resume = CODEX_RESUME_PROMPT if agent == "codex" else RESUME_PROMPT
        argv = runner.argv(
            prompt if runs == 0 else resume,
            model=model,
            budget_usd=round(left, 2),
            session=session,
            work_dir=work_dir,
            runs=runs,
        )
        code, out, err, timed_out = _run(
            argv, repo=repo, env=env, timeout=deadline - time.monotonic()
        )
        log = f"{out}\n{err}".strip()
        last = runner.result(code, out, timed_out, work_dir, runs, session)
        runs += 1
        session = last.session or session
        if last.usage:
            usage.append(last.usage)
        if agent == "claude":
            if last.cost_usd is None:
                notes.append(f"run {runs}'s cost couldn't be read from Claude's output")
            spent = None if spent is None or last.cost_usd is None else spent + last.cost_usd
        if agent == "codex":
            message = work_dir / f"codex-last-{runs - 1}.md"
            if message.is_file() and message.read_text().strip():
                shutil.copyfile(message, report)

        if report.is_file() or timed_out or code != 0:
            break
        # Resume only when it can't overspend: Claude reports its cost, Copilot can't report
        # what's left of a credit cap, and Codex has no cap but the deadline.
        if agent == "claude" and spent is None:
            skipped = "not resumed past an unknown spend"
        elif agent == "claude" and budget_usd - spent < MIN_RESUME_USD:
            skipped = f"not resumed: ${spent:.2f} of ${budget_usd} already spent"
        elif agent == "copilot" and max_ai_credits:
            skipped = "not resumed: Copilot can't report what's left of max-ai-credits"
        elif not session:
            skipped = "not resumed: the first run left no session"
        elif deadline - time.monotonic() < MIN_RESUME_SECONDS:
            skipped = "not resumed: too little time left before the deadline"
        if skipped:
            break

    assert last is not None
    written = report.is_file()
    if written and not last.timed_out and last.returncode == 0:
        status, error = "ok", ""
    elif last.timed_out:
        status, error = "timeout", f"the review hit its {int(timeout_s)}s limit"
    elif agent == "claude" and "error_max_budget" in log:
        status, error = "budget", f"the ${budget_usd} budget ran out"
    elif _AUTH.search(log):
        status, error = "auth", "the agent's credential was rejected"
    elif last.returncode not in (0, None):
        status, error = "error", f"{agent} exited with status {last.returncode}"
    else:
        status, error = "no_report", f"the review ended without writing {REPORT}"
        if skipped:
            error = f"{error} ({skipped})"
    if status != "ok" and log:
        error = f"{error}: {log[-1500:]}"
    return ReviewResult(
        status=status,
        agent=agent,
        report_written=written,
        cost_usd=round(spent, 4) if agent == "claude" and spent is not None else None,
        usage=usage,
        runs=runs,
        error=error,
        notes=notes,
    )
