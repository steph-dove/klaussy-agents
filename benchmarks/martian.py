"""Score the review skill on Martian's offline Code Review Bench.

https://github.com/withmartian/code-review-benchmark (MIT). Judging reuses
Martian's step-3 prompt and pairwise golden x candidate matching, run through the
`claude` CLI instead of their OpenAI-compatible endpoint. Opt-in and costs money:

    git clone https://github.com/withmartian/code-review-benchmark <martian-dir>
    KLAUSSY_RUN_BENCH=1 uv run python benchmarks/martian.py --martian-dir <martian-dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import runner  # noqa: E402

JUDGE_MODEL = "claude-sonnet-4-5-20250929"
DASHBOARD_JUDGE = "anthropic_claude-sonnet-4-5-20250929"

PILOT = [
    "https://github.com/ai-code-review-evaluation/sentry-greptile/pull/1",
    "https://github.com/grafana/grafana/pull/103633",
    "https://github.com/keycloak/keycloak/pull/37429",
    "https://github.com/calcom/cal.com/pull/10600",
    "https://github.com/ai-code-review-evaluation/discourse-graphite/pull/3",
]

PROFILES = {
    "strict": {"bug", "security", "concurrency", "data", "api"},
    "core": {"bug", "security", "concurrency", "data", "api", "perf", "test_gap", "doc_defect"},
    "all": {
        "bug",
        "security",
        "concurrency",
        "data",
        "api",
        "perf",
        "test_gap",
        "doc_defect",
        "style",
        "speculative",
    },
}

JUDGE_SYSTEM = "You are a precise code review evaluator. Always respond with valid JSON."

# Verbatim from Martian's step3_judge_comments.py so scores stay comparable.
JUDGE_PROMPT = """You are evaluating AI code review tools.
Determine if the candidate issue matches the golden (expected) comment.

Golden Comment (the issue we're looking for):
{golden_comment}

Candidate Issue (from the tool's review):
{candidate}

Instructions:
- Determine if the candidate identifies the SAME underlying issue as the golden comment
- Accept semantic matches - different wording is fine if it's the same problem
- Focus on whether they point to the same bug, concern, or code issue

Respond with ONLY a JSON object:
{{"reasoning": "brief explanation", "match": true/false, "confidence": 0.0-1.0}}"""


def load_golden(martian_dir: Path) -> dict[str, dict]:
    golden = {}
    for f in sorted((martian_dir / "offline" / "golden_comments").glob("*.json")):
        for entry in json.loads(f.read_text()):
            golden[entry["url"]] = {"source": f.stem, **entry}
    return golden


def judge(golden_comments: list[dict], candidates: list[str], model: str) -> dict:
    """Martian's step-3 matching: best-confidence candidate per golden comment."""
    pairs = [(g, c) for g in golden_comments for c in candidates]

    def one(pair):
        g, c = pair
        try:
            return runner.ask_claude_json(
                JUDGE_SYSTEM, JUDGE_PROMPT.format(golden_comment=g["comment"], candidate=c), model
            )
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    results = runner.parallel_map(one, pairs)
    matched_golden: dict[str, dict] = {}
    matched_candidates: set[str] = set()
    errors: list[str] = []
    cost = 0.0
    for (g, c), r in zip(pairs, results):
        cost += r.get("_cost_usd", 0.0)
        if r.get("error"):
            errors.append(r["error"])
            continue
        best = matched_golden.get(g["comment"], {}).get("confidence", 0.0)
        if r.get("match") and r.get("confidence", 0) > best:
            matched_golden[g["comment"]] = {
                "candidate": c,
                "confidence": r["confidence"],
                "reasoning": r.get("reasoning"),
            }
            matched_candidates.add(c)
    return {
        "true_positives": [
            {**g, **matched_golden[g["comment"]]}
            for g in golden_comments
            if g["comment"] in matched_golden
        ],
        "false_negatives": [g for g in golden_comments if g["comment"] not in matched_golden],
        "false_positives": [c for c in candidates if c not in matched_candidates],
        "judge_errors": len(errors),
        "judge_error_samples": sorted(set(errors))[:3],
        "judge_cost_usd": cost,
    }


def profile_counts(evaluation: dict, cats: set[str]) -> dict[str, int]:
    return {
        "tp": sum(1 for t in evaluation["true_positives"] if t["category"] in cats),
        "fp": len(evaluation["false_positives"]),
        "fn": sum(1 for f in evaluation["false_negatives"] if f["category"] in cats),
    }


def baselines(martian_dir: Path, urls: list[str], profile: str) -> dict[str, dict]:
    """Other tools' published results on the same PRs, under the same judge."""
    dash = json.loads((martian_dir / "offline/analysis/benchmark_dashboard.json").read_text())
    totals: dict[str, dict[str, int]] = {}
    for pr in dash["models"][DASHBOARD_JUDGE]["prs"]:
        if pr["url"] not in urls:
            continue
        for tool, m in pr["tool_metrics"].items():
            t = totals.setdefault(tool, {"tp": 0, "fp": 0, "fn": 0})
            for k in t:
                t[k] += m[profile][k]
    return {tool: {**t, **runner.prf1(**t)} for tool, t in totals.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Martian Code Review Bench")
    parser.add_argument("--martian-dir", type=Path, required=True)
    cache = Path.home() / ".cache" / "klaussy-bench"
    parser.add_argument("--work-dir", type=Path, default=cache / "repos")
    parser.add_argument("--out", type=Path, default=cache / "results" / "martian")
    parser.add_argument("--prs", nargs="*", help="Golden PR URLs (default: the 5-PR pilot)")
    parser.add_argument("--all", action="store_true", help="Run all 50 benchmark PRs")
    parser.add_argument("--model", help="Reviewer model (default: KLAUSSY_BENCH_MODEL or sonnet)")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--budget-usd", type=float, default=10.0, help="Per-PR review cap")
    parser.add_argument("--profile", choices=list(PROFILES), default="core")
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="klaussy init --skip-enrich (cheaper, less repo context)",
    )
    parser.add_argument("--instruction", default="", help="Extra user request for the review")
    parser.add_argument("--rejudge", action="store_true", help="Reuse saved reviews, re-judge")
    args = parser.parse_args()

    if os.environ.get("KLAUSSY_RUN_BENCH") != "1":
        sys.exit("Set KLAUSSY_RUN_BENCH=1: this runs paid agent reviews and judge calls.")

    golden = load_golden(args.martian_dir)
    urls = list(golden) if args.all else (args.prs or PILOT)
    args.out.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)

    per_pr = []
    for url in urls:
        entry = golden[url]
        slug = f"{entry['source']}-{url.rstrip('/').split('/')[-1]}"
        saved = args.out / f"{slug}.json"
        record = json.loads(saved.read_text()) if saved.exists() else None
        if record is None:
            print(f"[{slug}] preparing {url}", flush=True)
            pr = runner.fetch_pr(url)
            repo = runner.prepare_repo(
                pr,
                args.work_dir.resolve() / slug,
                entry["source"].replace("_", "-"),
                enrich=not args.skip_enrich,
            )
            print(f"[{slug}] reviewing in {repo}", flush=True)
            review = runner.run_review(
                repo, model=args.model, budget_usd=args.budget_usd, instruction=args.instruction
            )
            failed = runner.review_failed(review)
            if failed:
                print(f"[{slug}] review failed, not scored or saved: {failed}", flush=True)
                continue
            record = {"url": url, "title": entry["pr_title"], "review": review}
            saved.write_text(json.dumps(record, indent=2))
        if "evaluation" not in record or args.rejudge or record["evaluation"]["judge_errors"]:
            findings = runner.parse_findings(record["review"]["report"])
            record["findings"] = findings
            print(f"[{slug}] judging {len(findings)} findings", flush=True)
            record["evaluation"] = judge(
                entry["comments"], [f["text"] for f in findings], args.judge_model
            )
        saved.write_text(json.dumps(record, indent=2))
        per_pr.append(record)

    cats = PROFILES[args.profile]
    totals = {"tp": 0, "fp": 0, "fn": 0}
    print(f"\nPer PR ({args.profile} profile):")
    excluded = [rec for rec in per_pr if rec["evaluation"]["judge_errors"]]
    for rec in per_pr:
        c = profile_counts(rec["evaluation"], cats)
        if rec not in excluded:
            for k in totals:
                totals[k] += c[k]
        r = rec["review"]
        print(
            f"  {rec['url']}\n    tp={c['tp']} fp={c['fp']} fn={c['fn']}"
            f"  findings={len(rec['findings'])}  review ${r['cost_usd'] or 0:.2f}"
            f"  {r['duration_s']:.0f}s  judge ${rec['evaluation']['judge_cost_usd']:.2f}"
            + ("" if r["report_written"] else "  (no REVIEW_OUTPUT.md)")
            + (
                f"  judge errors={rec['evaluation']['judge_errors']}, not scored"
                if rec["evaluation"]["judge_errors"]
                else ""
            )
        )
        if "phases" in r:
            print(f"    phases {r['phases']}")

    scored = [rec["url"] for rec in per_pr if rec not in excluded]
    if excluded:
        print(f"\n{len(excluded)} PR(s) left out for judge errors; rerun to re-judge them.")
        for rec in excluded:
            print(f"  {rec['url']}: {rec['evaluation'].get('judge_error_samples')}")
    table = baselines(args.martian_dir, scored, args.profile)
    table["klaussy-review"] = {**totals, **runner.prf1(**totals)}
    print(f"\n{len(scored)} PRs, {args.profile} profile, judge {args.judge_model}:")
    print(f"  {'tool':<22}{'prec':>7}{'recall':>8}{'F1':>7}{'F2':>7}{'TP':>5}{'FP':>5}{'FN':>5}")
    for tool, m in sorted(table.items(), key=lambda kv: -kv[1]["f1"]):
        mark = " <" if tool == "klaussy-review" else ""
        print(
            f"  {tool:<22}{m['precision']:>7.0%}{m['recall']:>8.0%}{m['f1']:>7.0%}"
            f"{m['f2']:>7.0%}{m['tp']:>5}{m['fp']:>5}{m['fn']:>5}{mark}"
        )
    summary = {"tools": table, "excluded_for_judge_errors": [rec["url"] for rec in excluded]}
    (args.out / f"summary-{args.profile}.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
