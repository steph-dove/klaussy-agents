"""ReviewBench agent: run the klaussy review skill on one pull request.

Implements https://github.com/review-bench/ReviewBench/blob/main/AGENT_CONTRACT.md.
Build from the repository root:

    docker build --platform linux/amd64 -f benchmarks/reviewbench.Dockerfile -t klaussy-review:dev .
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import runner  # noqa: E402

_LOCATION = re.compile(r"([\w./-]+\.\w+|[\w./-]*/[\w.-]+):(\d+)(?:\s*[-–]\s*(\d+))?")


def to_findings(report: str, producer: str) -> list[dict]:
    """The report's findings in contract form; findings with no file:line are dropped."""
    out = []
    for f in runner.parse_findings(report):
        m = _LOCATION.search(f["location"]) or _LOCATION.search(f["text"])
        if not m:
            print(f"agent: no file:line, dropped: {f['location']}", file=sys.stderr)
            continue
        start = int(m.group(2))
        end = max(start, int(m.group(3) or start))
        out.append(
            {
                "file": m.group(1).removeprefix("./"),
                "start_line": start,
                "end_line": end,
                "message": f["text"],
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


def main() -> None:
    env = os.environ
    for name in ("RB_NWO", "RB_PR_NUMBER", "RB_BASE", "RB_HEAD", "RB_OUT"):
        if not env.get(name):
            sys.exit(f"agent: missing {name}")
    agent = env.get("RB_AGENT", "klaussy-review")
    model = env.get("RB_CONFIG_MODEL", runner.DEFAULT_REVIEW_MODEL)
    instruction = env.get("RB_CONFIG_INSTRUCTION", "")
    print(f"agent: model={model} instruction={instruction!r}", file=sys.stderr)

    repo = Path("/tmp/review") / env["RB_NWO"].split("/")[1]
    prepare(Path(env.get("RB_REPO", "/work/repo")), repo, env["RB_BASE"], env["RB_HEAD"])
    runner._scaffold(repo, enrich=env.get("RB_CONFIG_ENRICH", "1") != "0")
    review = runner.run_review(repo, model=model, budget_usd=20.0, instruction=instruction)
    failed = runner.review_failed(review)
    if failed:
        sys.exit(f"agent: review failed: {failed}")

    findings = to_findings(review["report"], agent)
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
        f"agent: {len(findings)} finding(s), ${review['cost_usd']:.2f}, "
        f"{review['duration_s']:.0f}s",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
