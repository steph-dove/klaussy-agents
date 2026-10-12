"""ReviewBench agent: run the klaussy review skill on one pull request.

Implements https://github.com/review-bench/ReviewBench/blob/main/AGENT_CONTRACT.md.
Build from the repository root:

    docker build --platform linux/amd64 -f benchmarks/reviewbench.Dockerfile -t klaussy-review:dev .
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from klaussy import review_post


def to_findings(report: str, producer: str) -> list[dict]:
    """The report's findings in contract form; findings with no file:line are dropped."""
    out = []
    for f in review_post.parse_findings(report):
        where = f.place()
        if not where:
            print(f"agent: no file:line, dropped: {f.location}", file=sys.stderr)
            continue
        path, start, end = where
        out.append(
            {
                "file": path,
                "start_line": start,
                "end_line": end,
                "message": f.text,
                "producer": producer,
            }
        )
    return out


def prepare(src: Path, dest: Path, base: str, head: str) -> None:
    """Copy the mounted checkout and give it the `main`/`pr` branches the harness reviews."""
    shutil.copytree(src, dest, symlinks=True)
    git = ["git", "-C", str(dest)]
    merge_base = subprocess.run(
        [*git, "merge-base", base, head], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run([*git, "branch", "-f", "main", merge_base], check=True)
    subprocess.run([*git, "checkout", "-q", "-B", "pr", head], check=True)


DEFAULT_MODEL = "claude-sonnet-5-5"
# ReviewBench stops a pull request at 15 minutes; leave room to write findings after a timeout.
DEFAULT_TIMEOUT_S = 780


def review(repo: Path, work: Path, *, model: str, timeout_s: int, enrich: bool, head: str) -> dict:
    """Run `klaussy review --headless`, the runner the Action and hosted App use; the result JSON
    plus the report text."""
    cmd = [
        sys.executable,
        "-m",
        "klaussy",
        "review",
        "--headless",
        "--repo",
        str(repo),
        "--agent",
        "claude",
        "--model",
        model,
        "--base",
        "main",
        "--head-sha",
        head,
        "--repo-name",
        repo.name,
        "--budget-usd",
        "20",
        "--timeout",
        str(timeout_s),
        "--work-dir",
        str(work),
        "--out",
        str(work / "result.json"),
        "--diff-out",
        str(work / "pr.diff"),
        "--report-out",
        str(work / "REVIEW_OUTPUT.md"),
    ]
    if enrich:
        cmd.append("--enrich")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(f"agent: klaussy review exited {proc.returncode}", proc.stderr[-2000:], file=sys.stderr)
    result_file, report = work / "result.json", work / "REVIEW_OUTPUT.md"
    result = json.loads(result_file.read_text()) if result_file.is_file() else {}
    result["report"] = report.read_text() if report.is_file() else ""
    return result


def main() -> None:
    env = os.environ
    for name in ("RB_NWO", "RB_PR_NUMBER", "RB_BASE", "RB_HEAD", "RB_OUT"):
        if not env.get(name):
            sys.exit(f"agent: missing {name}")
    if env.get("RB_CONFIG_INSTRUCTION"):
        sys.exit("agent: RB_CONFIG_INSTRUCTION isn't passed through klaussy review --headless")
    agent = env.get("RB_AGENT", "klaussy-review")
    model = env.get("RB_CONFIG_MODEL", DEFAULT_MODEL)
    timeout_s = int(env.get("RB_CONFIG_TIMEOUT", DEFAULT_TIMEOUT_S))
    enrich = env.get("RB_CONFIG_ENRICH", "1") != "0"
    print(f"agent: model={model} timeout={timeout_s}s enrich={enrich}", file=sys.stderr)

    repo = Path("/tmp/review") / env["RB_NWO"].split("/")[1]
    prepare(Path(env.get("RB_REPO", "/work/repo")), repo, env["RB_BASE"], env["RB_HEAD"])
    result = review(
        repo,
        Path("/tmp/review-work"),
        model=model,
        timeout_s=timeout_s,
        enrich=enrich,
        head=env["RB_HEAD"],
    )
    # A review stopped by its time or budget limit still counts for the findings it wrote.
    if result.get("status") not in ("ok", "timeout", "budget") or not result["report"]:
        sys.exit(f"agent: review failed: {result.get('status')}: {result.get('error', '')[:500]}")

    findings = to_findings(result["report"], agent)
    pr = {
        "repo": f"https://github.com/{env['RB_NWO']}",
        "pr_number": int(env["RB_PR_NUMBER"]),
        "base": env["RB_BASE"],
        "head": env["RB_HEAD"],
    }
    Path(env["RB_OUT"]).write_text(
        json.dumps({"pr": pr, "agent": agent, "findings": findings}, indent=2)
    )
    print(
        f"agent: {len(findings)} finding(s), status {result.get('status')}, "
        f"cost {result.get('cost_usd')}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
