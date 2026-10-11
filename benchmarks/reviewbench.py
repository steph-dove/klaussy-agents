"""Run the review skill on ReviewBench pull requests locally, without the container.

Writes one contract findings file per pull request, ready for ReviewBench's judge
(`npm run judge -- --candidate <out>/findings ...`). Opt-in and runs paid reviews:

    KLAUSSY_RUN_BENCH=1 uv run python benchmarks/reviewbench.py \\
        --rb-dir <ReviewBench checkout> --work-dir <dir> --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import reviewbench_agent  # noqa: E402
import runner  # noqa: E402

MIRROR_ORG = "review-bench"
AGENT = "klaussy-review"


def task_key(task: dict) -> str:
    """The findings file name try-agent.sh and the judge use."""
    return f"{task['nwo'].replace('/', '_')}_{task['pr_number']}-{task['head'][:8]}"


def headless_review(path: Path, repo: str, key: str, args: argparse.Namespace) -> dict:
    """Review through `klaussy review --headless`, the runner the Action and hosted App use,
    in the dict shape run_task reads."""
    work = args.work_dir.resolve() / f"{key}-headless"
    shutil.rmtree(work, ignore_errors=True)  # a stale report must never be scored
    cmd = [
        sys.executable,
        "-m",
        "klaussy",
        "review",
        "--headless",
        "--repo",
        str(path),
        "--agent",
        "claude",
        "--base",
        "main",
        "--repo-name",
        repo,
        "--enrich",
        "--budget-usd",
        str(args.budget_usd),
        "--timeout",
        "3600",
        "--work-dir",
        str(work),
        "--out",
        str(work / "result.json"),
        "--diff-out",
        str(work / "pr.diff"),
    ]
    if args.model:
        cmd += ["--model", args.model]
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result = (
        json.loads((work / "result.json").read_text()) if (work / "result.json").exists() else {}
    )
    report = work / "REVIEW_OUTPUT.md"
    return {
        "report": report.read_text() if report.exists() else "",
        "report_written": report.exists(),
        "cost_usd": result.get("cost_usd") or 0.0,
        "duration_s": time.monotonic() - started,
        "error": None
        if result.get("status") == "ok" and proc.returncode == 0
        else (
            result.get("error")
            or proc.stderr[-1500:]
            or f"headless review exited {proc.returncode} with status {result.get('status')!r}"
        ),
        "phases": {"status": result.get("status"), "runs": result.get("runs")},
        "headless": result,
    }


def run_task(task: dict, args: argparse.Namespace) -> str:
    key = task_key(task)
    findings_file = args.out / "findings" / f"{key}.json"
    if findings_file.exists():
        return f"[{key}] already reviewed"
    owner, repo = task["nwo"].split("/")
    mirror = f"{owner}_{repo}"
    pr = runner.PullRequest(
        url=f"https://github.com/{task['nwo']}/pull/{task['pr_number']}",
        owner=MIRROR_ORG,
        repo=mirror,
        number=int(task["pr_number"]),
        title=task["title"],
        body=task.get("body") or "",
        merge_base=runner.merge_base(MIRROR_ORG, mirror, task["base"], task["head"]),
        head=task["head"],
    )
    print(f"[{key}] preparing", flush=True)
    path = runner.prepare_repo(pr, args.work_dir.resolve() / key, repo)
    print(f"[{key}] reviewing in {path}", flush=True)
    if args.headless:
        review = headless_review(path, repo, key, args)
    else:
        review = runner.run_review(
            path, model=args.model, budget_usd=args.budget_usd, instruction=args.instruction
        )
    (args.out / "reviews" / f"{key}.json").write_text(json.dumps(review, indent=2))
    failed = runner.review_failed(review)
    if failed:
        raise RuntimeError(f"review failed, no findings written: {failed}")
    findings = reviewbench_agent.to_findings(review["report"], AGENT)
    record = {
        "pr": {
            "repo": f"https://github.com/{task['nwo']}",
            "pr_number": int(task["pr_number"]),
            "base": task["base"],
            "head": task["head"],
        },
        "agent": AGENT,
        "findings": findings,
    }
    findings_file.write_text(json.dumps(record, indent=2))
    return (
        f"[{key}] {len(findings)} finding(s)  review ${review['cost_usd']:.2f} "
        f"{review['duration_s']:.0f}s\n    phases {review['phases']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ReviewBench, run locally")
    parser.add_argument("--rb-dir", type=Path, required=True, help="ReviewBench checkout")
    parser.add_argument("--set", choices=["test", "full"], default="test")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", help="Reviewer model (default: KLAUSSY_BENCH_MODEL or Opus 5.5)")
    parser.add_argument("--budget-usd", type=float, default=20.0, help="Per-PR review cap")
    parser.add_argument("--instruction", default="", help="Extra user request for the review")
    parser.add_argument("--workers", type=int, default=1, help="Pull requests run at once")
    parser.add_argument("--limit", type=int, help="Only the first N pull requests")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Review through `klaussy review --headless` instead of the bench runner",
    )
    args = parser.parse_args()

    if os.environ.get("KLAUSSY_RUN_BENCH") != "1":
        sys.exit("Set KLAUSSY_RUN_BENCH=1: this runs paid agent reviews.")
    manifest = "corpus/test/test.json" if args.set == "test" else "corpus/manifest.json"
    tasks = json.loads((args.rb_dir / manifest).read_text())[: args.limit]
    for sub in ("findings", "reviews"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    failures = []

    def one(task):
        try:
            print(run_task(task, args), flush=True)
        except Exception as e:
            failures.append(task_key(task))
            print(f"[{task_key(task)}] failed: {type(e).__name__}: {e}", flush=True)

    runner.parallel_map(one, tasks, workers=args.workers)
    done = len(list((args.out / "findings").glob("*.json")))
    print(f"\n{done}/{len(tasks)} pull requests have findings in {args.out / 'findings'}")
    if failures:
        sys.exit(f"Failed ({len(failures)}): {', '.join(failures)}")


if __name__ == "__main__":
    main()
