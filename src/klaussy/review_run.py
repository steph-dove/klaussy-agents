"""Run the review skill headless on a pull request checkout, with any supported agent.

The GitHub Action and the hosted review App both call this through
`klaussy review --headless`, so the checkout scrub, the command guards and the
agent invocations live in one place.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import site
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

from klaussy.secret_scan import redact
from klaussy.skills import sanitize_skill_namespace

REPORT = "REVIEW_OUTPUT.md"
RESUME_PROMPT = f"{REPORT} doesn't exist yet. Finish the review and write it."
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
# The review, and humanize, which it uses to write its comments.
REVIEW_SKILLS = ("review", "humanize")
# Where `klaussy init` writes skills for the agents the runner scaffolds.
SKILL_ROOTS = (".claude/skills", ".github/skills")
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
    "openai": ("OPENAI_API_KEY",),
}
WRITE_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN")
# `openai` runs Copilot CLI with OpenAI as its model provider, so it keeps Copilot's allow-list
# and confinement; the skill is rendered where Copilot reads it.
SKILL_BACKEND = {"claude": "claude", "copilot": "copilot", "openai": "copilot"}
OPENAI_PROVIDER = {
    "COPILOT_PROVIDER_BASE_URL": "https://api.openai.com/v1",
    "COPILOT_PROVIDER_TYPE": "openai",
    # Copilot's help: use the responses wire API for GPT-5 series models.
    "COPILOT_PROVIDER_WIRE_API": "responses",
}
DEFAULT_MODEL = {"claude": "claude-opus-5-5", "openai": "gpt-5.4"}


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
    error_text: str = ""
    denied: tuple[str, ...] = ()
    stop: str = ""


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
    root = repo.resolve()
    for path in sorted(paths):
        target = repo / path
        if not target.parent.resolve().is_relative_to(root):
            continue  # under a symlinked directory: nothing outside the checkout is touched
        # A symlinked conventions file goes even on the second pass, so it can't point the
        # reviewer at a file the PR picked.
        if drop_unknown or target.is_symlink():
            _remove(target)
        if _base_has(repo, base, path):
            _git(repo, "checkout", "-q", base, "--", path)


def _klaussy(*args: str, repo: Path, env: dict[str, str], timeout: float | None = None) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "klaussy", *args],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReviewRunError(f"klaussy {args[0]} ran past {int(exc.timeout)}s") from exc
    if proc.returncode != 0:
        raise ReviewRunError(f"klaussy {args[0]}: {proc.stderr or proc.stdout}")


@contextmanager
def scratch_worktree(repo: Path, work_dir: Path, name: str) -> Iterator[Path]:
    """A throwaway worktree of HEAD named `name`, since skills are named after their folder."""
    if name in ("", ".", "..") or Path(name).name != name:
        raise ReviewRunError(f"--repo-name must be the repo's bare name, not {name!r}")
    path = work_dir / "checkout" / name
    if path.exists():
        _git(repo, "worktree", "remove", "--force", str(path), check=False)
        _remove(path)
    _git(repo, "worktree", "add", "--detach", "--force", str(path), "HEAD")
    try:
        yield path
    finally:
        _git(repo, "worktree", "remove", "--force", str(path), check=False)
        _git(repo, "worktree", "prune", check=False)


def prepare_checkout(
    repo: Path,
    *,
    base: str,
    agent: str,
    diff_out: Path,
    enrich: bool = False,
    timeout_s: float | None = None,
) -> None:
    """Capture the PR diff, strip the PR's agent config, take conventions from `base` and
    render the review skill for `agent`."""
    # Taken before the reviewer runs, so posting never runs git on a checkout it could touch.
    diff = _git(repo, "diff", "--no-ext-diff", "--no-textconv", f"{base}...HEAD").stdout
    diff_out.write_bytes(diff)

    for top in (".claude", ".claude/rules", ".github", ".github/instructions"):
        if (repo / top).is_symlink():
            (repo / top).unlink()
    # os.walk doesn't follow symlinked directories, so a PR's symlink can't point the sweep
    # outside the checkout; links that lead outside it go, so the reviewer can't read through one.
    inside = repo.resolve()
    for root, dirs, files in os.walk(repo):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in [*dirs, *files]:
            link = Path(root) / name
            if link.is_symlink() and not link.resolve().is_relative_to(inside):
                link.unlink()
                if name in dirs:
                    dirs.remove(name)
        if Path(root) != repo and ".claude" in dirs:
            _remove(Path(root) / ".claude")
            dirs.remove(".claude")
    for path in PR_AGENT_CONFIG:
        _remove(repo / path)
    _restore_conventions(repo, base, drop_unknown=True)

    # `init --enrich` runs a model over the PR's files, so it gets no token that can write and
    # no other agent's credential.
    env = _without_foreign_credentials(agent) | {"PYTHONSAFEPATH": "1"}
    branch = base.removeprefix("origin/")
    backend = SKILL_BACKEND[agent]
    if not (repo / "CLAUDE.md").is_file():
        flags = [] if enrich and agent == "claude" else ["--skip-enrich"]
        _klaussy(
            "init",
            "--repo",
            str(repo),
            "-b",
            branch,
            "--agents",
            backend,
            "--force",
            *flags,
            repo=repo,
            env=env,
            timeout=timeout_s,
        )
    # init can regenerate conventions the base already has; the base's win, and the review
    # skill is built from them afterwards.
    _restore_conventions(repo, base, drop_unknown=False)
    # Only what the review uses: every other skill is context the agent re-sends on each call.
    for skills_root in SKILL_ROOTS:
        _remove(repo / skills_root)
    _klaussy(
        "skills",
        "--repo",
        str(repo),
        "-b",
        branch,
        "--agents",
        backend,
        "--only",
        ",".join(REVIEW_SKILLS),
        "--force",
        repo=repo,
        env=env,
    )
    for path in SCAFFOLD_WIDENERS:
        _remove(repo / path)


def install_guards(guard_dir: Path) -> dict[str, str]:
    """Write the git and klaussy wrappers and return the env that puts them first on PATH."""
    guard_dir = guard_dir.resolve()
    guard_dir.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if not git:
        raise ReviewRunError("git isn't on PATH")
    found = shutil.which("klaussy")
    klaussy = shlex.quote(found) if found else f"{shlex.quote(sys.executable)} -m klaussy"
    real = {"REAL_GIT": shlex.quote(git), "REAL_KLAUSSY": klaussy}
    guards = resources.files("klaussy").joinpath("templates").joinpath("review-guards")
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


def _without_foreign_credentials(agent: str) -> dict[str, str]:
    others = {name for key, names in CREDENTIALS.items() if key != agent for name in names}
    return {k: v for k, v in os.environ.items() if k not in WRITE_TOKENS and k not in others}


def agent_env(agent: str, guard_env: dict[str, str], home: Path | None = None) -> dict[str, str]:
    """The environment the agent runs in: no token that writes, no other agent's credential,
    and with `home`, none of the operator's skills, plugins, MCP servers or settings."""
    env = _without_foreign_credentials(agent)
    env.update(guard_env)
    if home is not None:
        home.mkdir(parents=True, exist_ok=True)
        env.update(
            HOME=str(home),
            XDG_CONFIG_HOME=str(home / ".config"),
            CLAUDE_CONFIG_DIR=str(home / ".claude"),
            COPILOT_HOME=str(home / ".copilot"),
            # A `pip install --user` klaussy lives under the real home; the guards still need it.
            PYTHONUSERBASE=env.get("PYTHONUSERBASE") or site.getuserbase(),
        )
    if agent == "claude":
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if agent == "openai":
        env.update(OPENAI_PROVIDER, COPILOT_PROVIDER_API_KEY=env.pop("OPENAI_API_KEY", ""))
    return env


def review_prompt(repo_name: str, base: str, *, include_nits: bool) -> str:
    skill = f"{sanitize_skill_namespace(repo_name)}-review"
    nits = "Include nits: report Warn and Nit findings too. " if include_nits else ""
    return (
        f"Use the {skill} skill to review this branch (HEAD) against `{base}`. {nits}"
        f"There is no one to answer questions: make reasonable calls yourself. "
        f"Commands already run from the checkout root, so don't `cd` first, and read files with "
        f"your file-reading tool rather than `cat`. "
        f"Finish by writing {REPORT}."
    )


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the agent and what it started; Windows has no process groups, so just the agent."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        pass


def _run(
    argv: list[str], *, repo: Path, env: dict[str, str], timeout: float
) -> tuple[int | None, str, str, bool]:
    """(returncode, stdout, stderr, timed_out); a timeout kills the agent and everything it
    started, and keeps whatever was printed."""
    try:
        proc = subprocess.Popen(
            argv,
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as exc:
        return 127, "", f"couldn't start {argv[0]}: {exc}", False
    try:
        out, err = proc.communicate(timeout=max(timeout, 1))
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            # A grandchild that outlived the kill still holds the pipes; stop waiting on it.
            out, err = "", ""
        return None, out or "", err or "", True
    return proc.returncode, out, err, False


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
            model or DEFAULT_MODEL["claude"],
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
            str(data.get("result", "")) if data.get("is_error") else "",
            stop=str(data.get("subtype", "")),
        )


def _session_errors(stdout: str) -> str:
    """Copilot's own `session.error` messages; it reports failures in its event stream, not on
    stderr, as "authentication: Authentication failed with provider ... (HTTP 401)"."""
    errors = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "session.error":
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            errors.append(f"{data.get('errorType', 'error')}: {data.get('message', '')}".strip())
    return "\n".join(errors)


def _denied_calls(stdout: str) -> tuple[str, ...]:
    """Tool calls Copilot refused, as "tool: command"; a headless run gets "denied" for anything
    off the allow-list instead of a prompt."""
    started: dict[str, str] = {}
    denied = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
            continue
        data = event["data"]
        if event.get("type") == "tool.execution_start":
            args = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
            what = args.get("command") or args.get("path") or ""
            started[str(data.get("toolCallId"))] = f"{data.get('toolName')}: {str(what)[:120]}"
        elif event.get("type") == "tool.execution_complete":
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            if error.get("code") == "denied":
                denied.append(started.get(str(data.get("toolCallId")), "unknown tool"))
    return tuple(redact(call) for call in denied)


class Copilot:
    key = "copilot"
    allowed = (
        f"write({REPORT})",
        "shell(cd)",
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
            "--secret-env-vars=COPILOT_GITHUB_TOKEN,COPILOT_PROVIDER_API_KEY",
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
        return AgentRun(
            returncode,
            stdout,
            session,
            None,
            usage,
            timed_out,
            _session_errors(stdout),
            _denied_calls(stdout),
        )


AGENTS = ("claude", "copilot", "openai")


def make_agent(name: str, *, max_ai_credits: str | None = None):
    if name == "claude":
        return Claude()
    if name in ("copilot", "openai"):
        # A BYOK OpenAI run isn't billed in Copilot credits, so the credit cap doesn't apply.
        return Copilot(max_ai_credits if name == "copilot" else None)
    raise ValueError(f"agent must be one of {', '.join(AGENTS)}, not {name!r}")


_AUTH = re.compile(r"authentication|unauthori[sz]ed|invalid (api )?key|\b401\b|access denied", re.I)


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
    # An agent that authenticates from the environment needs nothing from the operator's home;
    # one on a local login keeps it, since that's where the login lives.
    from_env = any(os.environ.get(name) for name in CREDENTIALS[agent])
    home = (work_dir / "home").resolve() if from_env else None
    env = agent_env(agent, install_guards(work_dir / "guard"), home)
    report = repo / REPORT
    deadline = time.monotonic() + timeout_s
    prompt = review_prompt(repo_name, base, include_nits=include_nits)
    session = None if agent == "claude" else str(uuid.uuid4())
    model = model or DEFAULT_MODEL.get(agent)
    spent: float | None = 0.0
    usage: list[dict] = []
    runs = 0
    last: AgentRun | None = None
    log = ""
    auth_text = ""
    skipped = ""
    notes: list[str] = []

    while runs < 2:
        left = budget_usd - (spent or 0.0)
        argv = runner.argv(
            prompt if runs == 0 else RESUME_PROMPT,
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
        (work_dir / f"agent-run-{runs + 1}.out").write_text(out)
        (work_dir / f"agent-run-{runs + 1}.err").write_text(err)
        last = runner.result(code, out, timed_out, work_dir, runs, session)
        # Only the agent's own error text, never its event stream, which carries tool output.
        auth_text = f"{err}\n{last.error_text}"
        runs += 1
        session = last.session or session
        if last.usage:
            usage.append(last.usage)
        if last.denied:
            shown = "; ".join(last.denied[:5])
            more = f" (+{len(last.denied) - 5} more)" if len(last.denied) > 5 else ""
            notes.append(f"run {runs} was refused {len(last.denied)} tool call(s): {shown}{more}")
        if agent == "claude":
            if last.cost_usd is None:
                notes.append(f"run {runs}'s cost couldn't be read from Claude's output")
            spent = None if spent is None or last.cost_usd is None else spent + last.cost_usd

        if report.is_file() or timed_out or code != 0 or runs >= 2:
            break
        # Resume only when it can't overspend: Claude reports its cost, and Copilot can't
        # report what's left of a credit cap.
        if agent == "claude" and spent is None:
            skipped = "not resumed past an unknown spend"
        elif agent == "claude" and budget_usd - spent < MIN_RESUME_USD:
            skipped = f"not resumed: ${spent:.2f} of ${budget_usd} already spent"
        elif agent == "copilot" and max_ai_credits:
            skipped = "not resumed: Copilot can't report what's left of max-ai-credits"
        elif agent == "openai":
            skipped = "not resumed: an OpenAI run has no spending cap to resume within"
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
    elif last.stop == "error_max_budget_usd":
        status, error = "budget", f"the ${budget_usd} budget ran out"
    elif last.returncode not in (0, None) and _AUTH.search(auth_text):
        status, error = "auth", "the agent's credential was rejected"
    elif last.returncode not in (0, None):
        status, error = "error", f"{agent} exited with status {last.returncode}"
    else:
        status, error = "no_report", f"the review ended without writing {REPORT}"
        if skipped:
            error = f"{error} ({skipped})"
    if status != "ok" and (last.error_text or log):
        error = f"{error}: {last.error_text or log[-1500:]}"
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
