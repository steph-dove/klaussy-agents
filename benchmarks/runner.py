"""Benchmark-agnostic plumbing: rebuild a GitHub PR locally, run the review skill on it.

The PR becomes a two-commit repo: `main` at the merge base and `pr` holding the
PR's tree as one commit, so the skill sees exactly the PR diff and nothing else.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REVIEW_MODEL = "claude-sonnet-4-6"

_PR_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")
_FINDING = re.compile(r"^\*\*(?P<meta>[^*\n]*·[^*\n]*)\*\*\s*$", re.MULTILINE)


@dataclass
class PullRequest:
    url: str
    owner: str
    repo: str
    number: int
    title: str
    body: str
    merge_base: str
    head: str


def _run(args: list[str], cwd: Path | None = None, timeout: int = 1800) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])} failed: {proc.stderr[-1500:]}")
    return proc.stdout


def merge_base(owner: str, repo: str, base: str, head: str) -> str:
    out = _run(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo}/compare/{base}...{head}",
            "--jq",
            ".merge_base_commit.sha",
        ]
    )
    return out.strip()


def fetch_pr(url: str) -> PullRequest:
    owner, repo, number = _PR_URL.search(url).groups()
    pr = json.loads(_run(["gh", "pr", "view", url, "--json", "title,body,baseRefOid,headRefOid"]))
    return PullRequest(
        url=url,
        owner=owner,
        repo=repo,
        number=int(number),
        title=pr["title"],
        body=pr.get("body") or "",
        merge_base=merge_base(owner, repo, pr["baseRefOid"], pr["headRefOid"]),
        head=pr["headRefOid"],
    )


def prepare_repo(pr: PullRequest, work_dir: Path, name: str, *, enrich: bool = True) -> Path:
    """Materialize `pr` under work_dir/name with klaussy scaffolded; reuse it if present.

    `name` becomes the skill namespace, so give each PR its own work_dir.
    """
    dest = work_dir / name
    if (dest / ".claude" / "skills" / f"{name}-review" / "SKILL.md").exists():
        (dest / "REVIEW_OUTPUT.md").unlink(missing_ok=True)
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    git = ["git", "-c", "user.name=bench", "-c", "user.email=bench@localhost"]
    _run(["git", "init", "-q", "-b", "main"], cwd=dest)
    remote = f"https://github.com/{pr.owner}/{pr.repo}.git"
    _run(["git", "fetch", "-q", "--depth", "1", remote, pr.merge_base, pr.head], cwd=dest)
    _run(["git", "reset", "-q", "--hard", pr.merge_base], cwd=dest)
    _run(["git", "checkout", "-q", "-b", "pr"], cwd=dest)
    _run(["git", "read-tree", "-u", "--reset", pr.head], cwd=dest)
    _run([*git, "commit", "-q", "--no-verify", "-m", pr.title, "-m", pr.body], cwd=dest)
    _scaffold(dest, enrich=enrich)
    return dest


def _scaffold(repo: Path, *, enrich: bool) -> None:
    """Run `klaussy init` and hide its output from git so the review sees only the PR."""
    before = set(_run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo).split())
    cmd = ["klaussy", "init", "--repo", str(repo), "-b", "main", "--agents", "claude"]
    _run(cmd if enrich else [*cmd, "--skip-enrich"], cwd=repo, timeout=3600)
    _run(["git", "checkout", "-q", "--", "."], cwd=repo)
    after = set(_run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo).split())
    tops = sorted({p.split("/")[0] for p in after - before})
    with open(repo / ".git" / "info" / "exclude", "a") as f:
        f.write("".join(f"/{t}\n" for t in tops))
        f.write("/REVIEW_OUTPUT.md\n")


def run_review(
    repo: Path, *, model: str | None = None, budget_usd: float = 10.0, instruction: str = ""
) -> dict:
    prompt = (
        f"Use the {repo.name}-review skill to review this branch (`pr`) against `main`. "
        f"{instruction} "
        "There is no remote and no one to answer questions: make reasonable calls yourself "
        "and finish by writing REVIEW_OUTPUT.md."
    )
    proc = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "bypassPermissions",
            "--model",
            model or os.environ.get("KLAUSSY_BENCH_MODEL", DEFAULT_REVIEW_MODEL),
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-budget-usd",
            str(budget_usd),
            "--strict-mcp-config",
            "--no-session-persistence",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    (repo / ".git" / "bench-stream.jsonl").write_text(proc.stdout)
    trace, meta = _parse_stream(proc.stdout)
    if not meta:
        meta = {"error": proc.stderr[-1500:] or proc.stdout[-1500:]}
    report = repo / "REVIEW_OUTPUT.md"
    return {
        "report": report.read_text() if report.exists() else meta.get("result", ""),
        "report_written": report.exists(),
        "cost_usd": meta.get("total_cost_usd"),
        "cost_usd_per_result": meta.get("costs", []),
        "duration_s": (meta.get("duration_ms") or 0) / 1000,
        "num_turns": meta.get("num_turns"),
        "error": meta.get("error")
        or (meta.get("subtype") not in (None, "success") and meta["subtype"])
        or (meta.get("is_error") and (meta.get("result") or "is_error")),
        "phases": review_phases(trace),
        "trace": trace,
    }


def _parse_stream(stdout: str) -> tuple[list[dict], dict]:
    """Tool calls from a stream-json run, sub-agents' included, plus the final result event.

    Agent calls also keep their full prompt and returned text, which is where lens
    findings and validation verdicts live. A background agent's text arrives later in
    a notification naming its agentId, so that is matched back to the call too.
    """
    trace, result, agents, by_agent_id, costs = [], {}, {}, {}, []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            result = event
            costs.append(event.get("total_cost_usd"))
        late = [aid for aid in by_agent_id if aid in line]
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                arg = block.get("input") or {}
                detail = next(
                    (
                        arg[k]
                        for k in ("skill", "file_path", "command", "description")
                        if arg.get(k)
                    ),
                    "",
                )
                call = {
                    "tool": block.get("name", ""),
                    "detail": str(detail)[:300],
                    "subagent": bool(event.get("parent_tool_use_id")),
                }
                if call["tool"] in ("Agent", "Task"):
                    call["prompt"] = arg.get("prompt", "")
                    agents[block.get("id")] = call
                trace.append(call)
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in agents:
                content = block.get("content")
                if isinstance(content, list):
                    content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                content = content or ""
                launched = re.search(r"agentId: (\w+)", content)
                if launched:
                    by_agent_id[launched.group(1)] = agents[block["tool_use_id"]]
                    continue
                agents[block["tool_use_id"]]["output"] = content
        for aid in late:
            call = by_agent_id[aid]
            call["output"] = (call.get("output", "") + "\n" + _event_text(event)).strip()
    if result:
        result = {**result, "costs": costs}
    return trace, result


def _event_text(event: dict) -> str:
    content = (event.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict):
            inner = block.get("text") or block.get("content")
            if isinstance(inner, list):
                inner = "\n".join(c.get("text", "") for c in inner if isinstance(c, dict))
            parts.append(inner or "")
    return "\n".join(parts) or json.dumps(event)[:20000]


def review_phases(trace: list[dict]) -> dict:
    """Which parts of the review skill the run actually touched."""

    def read(name: str) -> bool:
        return any(t["tool"] == "Read" and t["detail"].endswith(name) for t in trace)

    return {
        "skill_invoked": any(
            t["tool"] == "Skill" or t["detail"].endswith("-review/SKILL.md") for t in trace
        ),
        "review_prep": any("review-prep" in t["detail"] for t in trace),
        "read_claude_md": read("CLAUDE.md"),
        "parallel_path": read("parallel.md"),
        "subagents": sum(1 for t in trace if t["tool"] in ("Agent", "Task")),
        "validation_rubric_read": read("lens-validation.md"),
    }


def review_failed(review: dict) -> str | None:
    """Why a review can't be scored, or None. An empty report would score as a clean pass."""
    if review.get("error"):
        return str(review["error"])[:300]
    if not review.get("report_written"):
        return "no REVIEW_OUTPUT.md written"
    return None


def parse_findings(report: str) -> list[dict]:
    """Split a REVIEW_OUTPUT.md into findings using the skill's `**Sev · Cat · loc**` lines."""
    marks = list(_FINDING.finditer(report))
    findings = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(report)
        body = report[m.end() : end]
        body = re.split(r"^\*\*Verdict:|^#{1,3} ", body, maxsplit=1, flags=re.MULTILINE)[0]
        parts = [p.strip(" `") for p in m.group("meta").split("·")]
        findings.append(
            {
                "severity": parts[0],
                "category": parts[1] if len(parts) > 2 else "",
                "location": parts[-1],
                "text": f"{m.group('meta').strip()}\n{body.strip()}",
            }
        )
    return findings


def ask_claude_json(system: str, prompt: str, model: str) -> dict:
    proc = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--system-prompt",
            system,
            "--tools",
            "",
            "--model",
            model,
            "--output-format",
            "json",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--setting-sources",
            "",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed ({proc.returncode}): {proc.stderr[-1500:]}")
    meta = json.loads(proc.stdout)
    if meta.get("is_error"):
        raise RuntimeError(
            f"claude -p returned an error: {meta.get('result') or meta.get('subtype')}"
        )
    text = meta.get("result", "").strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    out = json.loads(text)
    out["_cost_usd"] = meta.get("total_cost_usd") or 0.0
    return out


def prf1(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    f2 = 5 * p * r / (4 * p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f1, "f2": f2}


def parallel_map(fn, items: list, workers: int = 8) -> list:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
