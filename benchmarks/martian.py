"""Score the review skill on Martian's offline Code Review Bench.

https://github.com/withmartian/code-review-benchmark (MIT). Scoring runs Martian's
own extraction (step 2), dedup (step 2.5) and pairwise judge (step 3) prompts, read
from your checkout, through the `claude` CLI instead of their OpenAI-compatible
endpoint. Each review is scored as written and cut to Medium and above. Opt-in and
uses model calls:

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

SEVERE = {"Blocker", "High", "Medium"}

EXTRACT_SYSTEM = "You extract code review issues from comments. Always respond with valid JSON."
DEDUP_SYSTEM = "You group duplicate code review comments. Always respond with valid JSON only."
JUDGE_SYSTEM = "You are a precise code review evaluator. Always respond with valid JSON."


def load_prompts(martian_dir: Path) -> dict[str, str]:
    """Martian's extraction, dedup and judge prompts, read from the checkout."""
    src = martian_dir / "offline" / "code_review_benchmark"
    return {
        **runner.load_constants(src / "step2_extract_comments.py", {"EXTRACT_PROMPT"}),
        **runner.load_constants(src / "step2_5_dedup_candidates.py", {"STRICT_PROMPT"}),
        **runner.load_constants(src / "step3_judge_comments.py", {"JUDGE_PROMPT"}),
    }


def load_golden(martian_dir: Path) -> dict[str, dict]:
    golden = {}
    for f in sorted((martian_dir / "offline" / "golden_comments").glob("*.json")):
        for entry in json.loads(f.read_text()):
            golden[entry["url"]] = {"source": f.stem, **entry}
    return golden


def extract(report: str, prompts: dict, model: str) -> tuple[list[str], float]:
    """Martian step 2: split the whole review text into separate issues."""
    if len(report.strip()) < 20:
        return [], 0.0
    out = runner.ask_claude_json(
        EXTRACT_SYSTEM, prompts["EXTRACT_PROMPT"].format(comment=report), model
    )
    issues = out.get("issues")
    if not isinstance(issues, list) or not all(isinstance(i, str) for i in issues):
        raise ValueError(f"extraction returned no issues list: {str(out)[:200]}")
    return issues, out["_cost_usd"]


def dedup(candidates: list[str], prompts: dict, model: str) -> tuple[list[list[int]], float, bool]:
    """Martian step 2.5: group candidates that are the same issue; True if it fell back."""
    singletons = [[i] for i in range(len(candidates))]
    if len(candidates) < 2:
        return singletons, 0.0, False
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(candidates))
    out = runner.ask_claude_json(
        DEDUP_SYSTEM, prompts["STRICT_PROMPT"].format(candidates=numbered), model
    )
    groups = out.get("groups") or []
    if sorted(i for g in groups for i in g) != list(range(len(candidates))):
        return singletons, out["_cost_usd"], True
    return groups, out["_cost_usd"], False


def judge(
    golden_comments: list[dict],
    candidates: list[str],
    groups: list[list[int]],
    prompts: dict,
    model: str,
    samples: int,
) -> dict:
    """Martian step 3; majority voting stands in for temperature 0, which the CLI can't set."""
    calls = [(g, c) for g in golden_comments for c in candidates for _ in range(samples)]

    def one(call):
        g, c = call
        try:
            return runner.ask_claude_json(
                JUDGE_SYSTEM,
                prompts["JUDGE_PROMPT"].format(golden_comment=g["comment"], candidate=c),
                model,
            )
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    results = runner.parallel_map(one, calls)
    votes: dict[tuple[str, str], list[dict]] = {}
    errors: list[str] = []
    cost = 0.0
    for (g, c), r in zip(calls, results):
        cost += r.get("_cost_usd", 0.0)
        if r.get("error"):
            errors.append(r["error"])
        else:
            votes.setdefault((g["comment"], c), []).append(r)

    siblings = {candidates[i]: {candidates[j] for j in grp} for grp in groups for i in grp}
    matched_golden: dict[str, dict] = {}
    matched_candidates: set[str] = set()
    unjudged = 0
    for g in golden_comments:
        for c in candidates:
            vs = votes.get((g["comment"], c), [])
            if len(vs) * 2 <= samples:
                unjudged += 1
                continue
            yes = [v for v in vs if v.get("match")]
            if len(yes) * 2 <= len(vs):
                continue
            confidence = sum(v.get("confidence", 0) for v in yes) / len(yes)
            if confidence > matched_golden.get(g["comment"], {}).get("confidence", 0.0):
                matched_golden[g["comment"]] = {
                    "candidate": c,
                    "confidence": confidence,
                    "votes": f"{len(yes)}/{len(vs)}",
                    "reasoning": yes[0].get("reasoning"),
                }
                matched_candidates |= siblings.get(c, {c})
    return {
        "candidates": candidates,
        "groups": groups,
        "true_positives": [
            {**g, **matched_golden[g["comment"]]}
            for g in golden_comments
            if g["comment"] in matched_golden
        ],
        "false_negatives": [g for g in golden_comments if g["comment"] not in matched_golden],
        "false_positives": [c for c in candidates if c not in matched_candidates],
        "judge_errors": unjudged,
        "judge_error_samples": sorted(set(errors))[:3],
        "judge_cost_usd": cost,
    }


def evaluate(report: str, golden_comments: list[dict], prompts: dict, args) -> dict:
    try:
        candidates, cost = extract(report, prompts, args.judge_model)
        groups, dedup_cost, dedup_fallback = dedup(candidates, prompts, args.judge_model)
    except Exception as e:
        return {"judge_errors": 1, "judge_error_samples": [f"{type(e).__name__}: {e}"]}
    result = judge(golden_comments, candidates, groups, prompts, args.judge_model, args.samples)
    result["judge_cost_usd"] += cost + dedup_cost
    result["dedup_fallback"] = dedup_fallback
    return result


def severe_only(report: str) -> str:
    """The report cut to Blocker/High/Medium findings, as the default review writes it."""
    kept = [f["text"] for f in runner.parse_findings(report) if f["severity"] in SEVERE]
    return "\n\n".join(kept)


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
    parser.add_argument("--samples", type=int, default=3, help="Judge votes per pair")
    args = parser.parse_args()

    if os.environ.get("KLAUSSY_RUN_BENCH") != "1":
        sys.exit("Set KLAUSSY_RUN_BENCH=1: this runs paid agent reviews and judge calls.")

    golden = load_golden(args.martian_dir)
    prompts = load_prompts(args.martian_dir)
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
        evals = record.get("evaluations", {})
        report = record["review"]["report"]
        for variant, text in (("as-written", report), ("medium+", severe_only(report))):
            done = evals.get(variant)
            if done and not args.rejudge and not done["judge_errors"]:
                continue
            same = variant == "medium+" and evals.get("as-written") and text == report
            if same:
                evals[variant] = evals["as-written"]
                continue
            print(f"[{slug}] judging {variant}", flush=True)
            evals[variant] = evaluate(text, entry["comments"], prompts, args)
        record["evaluations"] = evals
        record.pop("evaluation", None)
        saved.write_text(json.dumps(record, indent=2))
        per_pr.append(record)

    summary = {}
    for variant in ("as-written", "medium+"):
        summary[variant] = report_variant(variant, per_pr, args)
    (args.out / f"summary-{args.profile}.json").write_text(json.dumps(summary, indent=2))


def report_variant(variant: str, per_pr: list[dict], args) -> dict:
    cats = PROFILES[args.profile]
    totals = {"tp": 0, "fp": 0, "fn": 0}
    print(f"\n== {variant} == per PR ({args.profile} profile):")
    excluded = []
    for rec in per_pr:
        ev = rec["evaluations"][variant]
        r = rec["review"]
        if ev["judge_errors"]:
            excluded.append(rec)
            print(f"  {rec['url']}\n    judge errors={ev['judge_errors']}, not scored")
            continue
        c = profile_counts(ev, cats)
        for k in totals:
            totals[k] += c[k]
        print(
            f"  {rec['url']}\n    tp={c['tp']} fp={c['fp']} fn={c['fn']}"
            f"  candidates={len(ev['candidates'])}  review ${r['cost_usd'] or 0:.2f}"
            f"  {r['duration_s']:.0f}s  judge ${ev['judge_cost_usd']:.2f}"
            + ("  (dedup fell back to singletons)" if ev.get("dedup_fallback") else "")
        )
        if variant == "as-written" and "phases" in r:
            print(f"    phases {r['phases']}")

    scored = [rec["url"] for rec in per_pr if rec not in excluded]
    if excluded:
        print(f"\n{len(excluded)} PR(s) left out for judge errors; rerun to re-judge them.")
        for rec in excluded:
            samples = rec["evaluations"][variant].get("judge_error_samples")
            print(f"  {rec['url']}: {samples}")
    table = baselines(args.martian_dir, scored, args.profile)
    table["klaussy-review"] = {**totals, **runner.prf1(**totals)}
    print(
        f"\n{len(scored)} PRs, {variant}, {args.profile} profile, judge {args.judge_model} "
        f"(majority of {args.samples}):"
    )
    print(f"  {'tool':<22}{'prec':>7}{'recall':>8}{'F1':>7}{'F2':>7}{'TP':>5}{'FP':>5}{'FN':>5}")
    for tool, m in sorted(table.items(), key=lambda kv: -kv[1]["f1"]):
        mark = " <" if tool == "klaussy-review" else ""
        print(
            f"  {tool:<22}{m['precision']:>7.0%}{m['recall']:>8.0%}{m['f1']:>7.0%}"
            f"{m['f2']:>7.0%}{m['tp']:>5}{m['fp']:>5}{m['fn']:>5}{mark}"
        )
    return {"tools": table, "excluded_for_judge_errors": [rec["url"] for rec in excluded]}


if __name__ == "__main__":
    main()
