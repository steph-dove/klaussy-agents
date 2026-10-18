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
from klaussy.review_run import EFFORTS


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
    # A Git LFS checkout's hooks and filters fail every checkout without git-lfs installed.
    for key, value in (
        ("core.hooksPath", os.devnull),
        ("filter.lfs.required", "false"),
        ("filter.lfs.process", ""),
        ("filter.lfs.smudge", ""),
        ("filter.lfs.clean", ""),
    ):
        subprocess.run([*git, "config", key, value], check=True)
    merge_base = subprocess.run(
        [*git, "merge-base", base, head], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run([*git, "branch", "-f", "main", merge_base], check=True)
    subprocess.run([*git, "checkout", "-q", "-B", "pr", head], check=True)


DEFAULT_MODEL = "claude-sonnet-5-5"


def agent_for(model: str) -> str:
    """GPT models run as `openai` (Copilot CLI with OpenAI as its provider); the rest as Claude."""
    return "openai" if model.lower().startswith("gpt-") else "claude"


def pr_info(path: Path) -> dict:
    """ReviewBench's pr.json (title and body among them); empty when it's missing or unreadable."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        print(f"agent: no PR title or description: {path} unreadable", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


# ReviewBench stops a pull request at 15 minutes; leave room to write findings after a timeout.
DEFAULT_TIMEOUT_S = 780


def review(
    repo: Path,
    work: Path,
    *,
    model: str,
    timeout_s: int,
    enrich: bool,
    head: str,
    pr: dict,
    effort: str | None = None,
    include_nits: bool = False,
) -> dict:
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
        agent_for(model),
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
    if effort:
        cmd += ["--effort", effort]
    if include_nits:
        cmd.append("--include-nits")
    if pr.get("title"):
        cmd += ["--pr-title", str(pr["title"])]
    if pr.get("body"):
        work.mkdir(parents=True, exist_ok=True)
        (work / "pr-body.md").write_text(str(pr["body"]))
        cmd += ["--pr-body-file", str(work / "pr-body.md")]
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
    include_nits = env.get("RB_CONFIG_INCLUDE_NITS", "0") != "0"
    # ReviewBench flags a config label whose value never shows up in the agent's output.
    effort = env.get("RB_CONFIG_EFFORT", "default").strip().lower()
    if effort not in ("default", *EFFORTS):
        sys.exit(f"agent: RB_CONFIG_EFFORT must be default or one of {', '.join(EFFORTS)}")
    backend = agent_for(model)
    if backend == "openai":
        # Effort and enrichment are Claude-only in the runner; a label for either would be false.
        if effort != "default":
            sys.exit("agent: RB_CONFIG_EFFORT only applies to Claude models")
        if "RB_CONFIG_ENRICH" in env and enrich:
            sys.exit("agent: RB_CONFIG_ENRICH only applies to Claude models")
        enrich = False
    # The run checks each label's value against this output, so echo them exactly as given.
    labels = " ".join(
        f"{k.removeprefix('RB_CONFIG_').lower()}={v}"
        for k, v in sorted(env.items())
        if k.startswith("RB_CONFIG_")
    )
    print(f"agent: labels {labels or '(none)'}", file=sys.stderr)
    print(
        f"agent: backend={backend} model={model} effort={effort} include_nits={include_nits} "
        f"timeout={timeout_s}s enrich={enrich}",
        file=sys.stderr,
    )

    repo = Path("/tmp/review") / env["RB_NWO"].split("/")[1]
    prepare(Path(env.get("RB_REPO", "/work/repo")), repo, env["RB_BASE"], env["RB_HEAD"])
    result = review(
        repo,
        Path("/tmp/review-work"),
        model=model,
        timeout_s=timeout_s,
        enrich=enrich,
        head=env["RB_HEAD"],
        pr=pr_info(Path(env.get("RB_PR_JSON", "/work/pr/pr.json"))),
        effort=None if effort == "default" else effort,
        include_nits=include_nits,
    )
    # A review stopped by its time or budget limit still counts for the findings it wrote.
    if result.get("status") not in ("ok", "timeout", "budget") or not result["report"]:
        sys.exit(f"agent: review failed: {result.get('status')}: {result.get('error', '')[:500]}")

    if review_post.unparsed_report(result["report"]):
        # Fail rather than submit nothing, so ReviewBench retries and the log shows the shape.
        print(f"agent: report head:\n{result['report'][:1500]}", file=sys.stderr)
        sys.exit("agent: the report isn't an approval but no findings parsed from it")
    findings = to_findings(result["report"], agent)
    if not findings:
        verdict = next((ln for ln in result["report"].splitlines() if "Verdict" in ln), "")
        print(f"agent: no findings; {verdict.strip() or 'no verdict line'}", file=sys.stderr)
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
