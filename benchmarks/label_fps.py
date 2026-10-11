"""Label a Martian run's false positives: real bug, near-miss, pre-existing, or wrong.

The golden lists are incomplete, so a finding that matches no golden comment isn't
necessarily wrong. An Opus call sees the PR diff, the golden comments and the
finding, and says which it is. Opt-in and uses model calls:

    KLAUSSY_RUN_BENCH=1 uv run python benchmarks/label_fps.py \\
        --results <martian --out dir> --work-dir <martian --work-dir>
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import runner  # noqa: E402

LABELS = ("near-miss", "real", "pre-existing", "wrong")
MAX_DIFF_CHARS = 80_000

SYSTEM = "You are a senior engineer auditing code review findings. Respond with JSON only."

PROMPT = """A code review tool reported the finding below on this pull request. It matched
none of the benchmark's expected comments. Decide which one of these it is:

- "near-miss": it describes the same underlying issue as one of the expected comments
- "real": a genuine defect that this PR introduces, which the expected comments don't cover
- "pre-existing": a genuine defect, but in code this PR didn't introduce or change
- "wrong": not supported by the code (misread logic, unreachable, already handled)

Expected comments:
{golden}

Finding:
{finding}

PR diff{truncated}:
```diff
{diff}
```

Respond with ONLY: {{"label": "near-miss|real|pre-existing|wrong", "reason": "one sentence"}}"""


def pr_diff(work_dir: Path, slug: str) -> str:
    checkouts = [p for p in (work_dir / slug).iterdir() if (p / ".git").exists()]
    if not checkouts:
        raise FileNotFoundError(f"no checkout under {work_dir / slug}")
    out = subprocess.run(
        ["git", "diff", "main...pr"], cwd=checkouts[0], capture_output=True, text=True
    )
    if out.returncode != 0:
        raise RuntimeError(f"git diff failed in {checkouts[0]}: {out.stderr[-500:]}")
    return out.stdout


def swr_false_positives(record: dict) -> tuple[list[str], list[str]] | None:
    """An SWR-Bench record's expected points and its unmatched predictions, or None."""
    verdict = record["verdict"]
    if "error" in verdict:
        return None
    gts = verdict["gt_points"] if record["change_introduced"] else []
    hit_by = {g["hit_by"] for g in gts if g["hit"] == "YES"}
    fps = [p["description"] for p in verdict["pred_points"] if p["id"] not in hit_by]
    return [g["description"] for g in gts], fps


def label(finding: str, golden: list[str], diff: str, model: str) -> dict:
    truncated = len(diff) > MAX_DIFF_CHARS
    prompt = PROMPT.format(
        golden="\n".join(f"- {g}" for g in golden) or "(none)",
        finding=finding,
        diff=diff[:MAX_DIFF_CHARS],
        truncated=" (truncated)" if truncated else "",
    )
    out = runner.ask_claude_json(SYSTEM, prompt, model)
    if out.get("label") not in LABELS:
        raise ValueError(f"unexpected label: {str(out)[:200]}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Martian false positives")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--variant", default="medium+")
    parser.add_argument("--model", default="claude-opus-5-5")
    args = parser.parse_args()

    if os.environ.get("KLAUSSY_RUN_BENCH") != "1":
        sys.exit("Set KLAUSSY_RUN_BENCH=1: this makes model calls.")

    jobs, skipped = [], []
    for f in sorted(args.results.glob("*.json")):
        if f.name.startswith(("summary", "fp-labels")):
            continue
        record = json.loads(f.read_text())
        found = swr_false_positives(record) if "verdict" in record else None
        if found is None:
            ev = (record.get("evaluations") or {}).get(args.variant)
            if ev and not ev.get("judge_errors"):
                golden = [g["comment"] for g in ev["true_positives"] + ev["false_negatives"]]
                found = golden, ev["false_positives"]
        if found is None:
            skipped.append(f.stem)
            continue
        golden, fps = found
        diff = pr_diff(args.work_dir, f.stem)
        jobs += [(f.stem, fp, golden, diff) for fp in fps]

    def one(job):
        slug, fp, golden, diff = job
        try:
            return slug, fp, label(fp, golden, diff, args.model)
        except Exception as e:
            return slug, fp, {"label": "error", "reason": f"{type(e).__name__}: {e}"}

    results = runner.parallel_map(one, jobs, workers=4)
    counts = collections.Counter(r["label"] for _, _, r in results)
    for slug, fp, r in results:
        print(f"[{r['label']:<12}] {slug}: {fp[:110]}\n    {r.get('reason', '')}")
    print(f"\n{len(results)} false positives: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if skipped:
        print(f"Not labeled (no complete {args.variant} score): {', '.join(skipped)}")
    (args.results / f"fp-labels-{args.variant}.json").write_text(
        json.dumps([{"pr": s, "finding": fp, **r} for s, fp, r in results], indent=2)
    )


if __name__ == "__main__":
    main()
