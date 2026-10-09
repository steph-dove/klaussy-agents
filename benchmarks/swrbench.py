"""Score the review skill on SWR-Bench (FSE 2026, arXiv:2509.01494).

https://github.com/ZZR0/SWRench (MIT). 1,000 Python PRs: 500 with reviewer-confirmed
issues, 500 clean. Judging reuses the official prompts from
`swrbench/evaluation_struct.py`, read from your checkout, run through the `claude`
CLI. Opt-in and costs money:

    git clone https://github.com/ZZR0/SWRench <swr-dir>
    KLAUSSY_RUN_BENCH=1 uv run python benchmarks/swrbench.py --swr-dir <swr-dir> --sample 10
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import runner  # noqa: E402

JUDGE_MODEL = "claude-sonnet-4-5-20250929"
JUDGE_SYSTEM = "You are a helpful assistant. Respond with JSON only."
DATASET = "data/swr_datasets_d5c5.jsonl"


def load_dataset(swr_dir: Path) -> list[dict]:
    with open(swr_dir / DATASET) as f:
        return [json.loads(line) for line in f]


def load_judge(swr_dir: Path) -> dict:
    """Pull the prompt constants out of evaluation_struct.py without importing it."""
    tree = ast.parse((swr_dir / "swrbench" / "evaluation_struct.py").read_text())
    wanted = {"EVAL_CLEAN_PROMPT", "EVAL_CHANGE_PROMPT", "CHANGE_TYPE_TEXT_MAP"}
    found = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in wanted
    }
    missing = wanted - found.keys()
    if missing:
        sys.exit(f"evaluation_struct.py no longer defines {sorted(missing)}")
    return found


def sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Half change PRs, half clean, so false positives on clean PRs are measured."""
    rng = random.Random(seed)
    change = [r for r in rows if r["change_introduced"]]
    clean = [r for r in rows if not r["change_introduced"]]
    return rng.sample(change, (n + 1) // 2) + rng.sample(clean, n // 2)


def _timeline_text(timeline: list[dict]) -> str:
    out = []
    for item in timeline:
        kind = item["type"]
        if kind == "comment":
            out.append(
                f"<Start of Comment>\nTime: {item['created_at']}\nAuthor: {item['user']}\n"
                f"Comment: {item['body']}\n<End of Comment>"
            )
        elif kind == "review_comment":
            replies = "".join(
                f"<Start of Sub Review Comment>\nTime: {c['created_at']}\nAuthor: {c['user']}\n"
                f"Comment: {c['body']}\n<End of Sub Review Comment>\n"
                for c in item["reply"]
            )
            out.append(
                f"<Start of Review Comment>\n<Start of Related Diff Hunk>\nFile: {item['path']}\n"
                f"{item['diff_hunk']}\n<End of Related Diff Hunk>\n{replies}<End of Review Comment>"
            )
        elif kind == "commit":
            out.append(
                f"<Start of Commit>\nTime: {item['date']}\nSHA: {item['sha']}\n"
                f"Author: {item['author']}\nMessage: {item['message']}\n<End of Commit>"
            )
        elif kind == "review":
            out.append(
                f"<Start of Review>\nTime: {item['created_at']}\nAuthor: {item['user']}\n"
                f"Review: {item['body']}\n<End of Review>"
            )
    return "\n".join(out)


def judge_prompt(instance: dict, review: str, judge: dict) -> str:
    """Port of create_change_pr_prompt / create_clean_pr_prompt."""
    review = review.replace("’", "'")
    if not instance["change_introduced"]:
        return judge["EVAL_CLEAN_PROMPT"].format(
            pr_title=instance["pr_title"],
            pr_statement=instance["pr_statement"],
            pred_review=review,
        )
    names = judge["CHANGE_TYPE_TEXT_MAP"]
    changes = []
    for i, change in enumerate(instance["changes"], 1):
        code = change["change_type"].split(" ")[0]
        changes.append(
            f"        <Ground Truth Change GT-POINT-{i}>\n"
            f"            Change Category: {code} {names[code]}\n"
            f"            Change Description: {change['change_discussion']['discussion_summary']}\n"
            f"            Change Code Snippet: {change['change_introducing']['code_snippet']}\n"
            f"        </Ground Truth Change GT-POINT-{i}>\n"
        )
    return judge["EVAL_CHANGE_PROMPT"].format(
        pr_title=instance["pr_title"],
        pr_statement=instance["pr_statement"],
        changes_description="\n".join(changes),
        ground_truth_reviews=_timeline_text(instance["pr_timeline"]),
        pred_review=review,
    )


def valid_verdict(result: dict, instance: dict) -> bool:
    """The checks verify_*_answer applies before a judgment counts."""
    if result.get("identified_as_good") not in ("YES", "NO"):
        return False
    if not isinstance(result.get("pred_points"), list):
        return False
    if not instance["change_introduced"]:
        return True
    gt = result.get("gt_points")
    return isinstance(gt, list) and len(gt) == len(instance["changes"])


def judge_review(instance: dict, review: str, judge: dict, model: str) -> dict:
    prompt = judge_prompt(instance, review, judge)
    cost = 0.0
    last_error = "no valid verdict"
    for _ in range(3):
        try:
            result = runner.ask_claude_json(JUDGE_SYSTEM, prompt, model)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            continue
        cost += result.pop("_cost_usd", 0.0)
        if valid_verdict(result, instance):
            for p in result["pred_points"]:
                p["change_category"] = str(p.get("change_category", "")).split(" ")[0]
            for gt, change in zip(result.get("gt_points", []), instance["changes"]):
                gt["change_category"] = change["change_type"].split(" ")[0]
            result["judge_cost_usd"] = cost
            return result
    return {"error": f"judge failed 3 attempts; last: {last_error}", "judge_cost_usd": cost}


def point_counts(instance: dict, verdict: dict, prefix: str = "") -> dict[str, int]:
    """Point-level tp/fp/fn, optionally limited to categories starting with `prefix`."""
    preds = [p for p in verdict["pred_points"] if p["change_category"].startswith(prefix)]
    if not instance["change_introduced"]:
        return {"tp": 0, "fp": len(preds), "fn": 0}
    gts = [g for g in verdict["gt_points"] if g["change_category"].startswith(prefix)]
    hit_by = {g["hit_by"] for g in verdict["gt_points"] if g["hit"] == "YES"}
    tp = sum(1 for p in preds if p["id"] in hit_by)
    if prefix:
        fn = sum(1 for g in gts if g["hit"] == "NO")
    else:
        fn = len(gts) - tp
    return {"tp": tp, "fp": len(preds) - tp, "fn": fn}


def flagged(verdict: dict) -> bool:
    return verdict["identified_as_good"] != "YES" and bool(verdict["pred_points"])


def summarize(records: list[dict]) -> dict:
    """Port of analyze_result's headline numbers: PR-level and point-level."""
    pr = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    points = {"tp": 0, "fp": 0, "fn": 0}
    functional = {"tp": 0, "fp": 0, "fn": 0}
    scored = [r for r in records if "error" not in r["verdict"]]
    for rec in scored:
        inst, verdict = rec["instance"], rec["verdict"]
        hit = flagged(verdict)
        if inst["change_introduced"]:
            pr["tp" if hit else "fn"] += 1
        else:
            pr["fp" if hit else "tn"] += 1
        for k, v in point_counts(inst, verdict).items():
            points[k] += v
        for k, v in point_counts(inst, verdict, "F").items():
            functional[k] += v
    total = sum(pr.values())
    return {
        "scored": len(scored),
        "judge_errors": len(records) - len(scored),
        "pr_level": {
            **pr,
            **runner.prf1(pr["tp"], pr["fp"], pr["fn"]),
            "accuracy": (pr["tp"] + pr["tn"]) / total if total else 0.0,
        },
        "point_level": {**points, **runner.prf1(**points)},
        "functional_points": {**functional, **runner.prf1(**functional)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SWR-Bench")
    cache = Path.home() / ".cache" / "klaussy-bench"
    parser.add_argument("--swr-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=cache / "repos")
    parser.add_argument("--out", type=Path, default=cache / "results" / "swrbench")
    parser.add_argument("--ids", nargs="*", help="instance_ids to run")
    parser.add_argument("--sample", type=int, default=10, help="Balanced change/clean sample")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", help="Reviewer model (default: KLAUSSY_BENCH_MODEL or sonnet)")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--budget-usd", type=float, default=10.0, help="Per-PR review cap")
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="klaussy init --skip-enrich (cheaper, less repo context)",
    )
    parser.add_argument("--rejudge", action="store_true", help="Reuse saved reviews, re-judge")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Rebuild repos and judge prompts; no review or judge calls (enrichment still runs)",
    )
    args = parser.parse_args()

    if os.environ.get("KLAUSSY_RUN_BENCH") != "1" and not (args.prepare_only and args.skip_enrich):
        sys.exit("Set KLAUSSY_RUN_BENCH=1: this runs paid agent reviews and judge calls.")

    rows = load_dataset(args.swr_dir)
    judge = load_judge(args.swr_dir)
    if args.ids:
        by_id = {r["instance_id"]: r for r in rows}
        chosen = [by_id[i] for i in args.ids]
    else:
        chosen = sample(rows, args.sample, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    records = []
    for inst in chosen:
        iid = inst["instance_id"]
        kind = "change" if inst["change_introduced"] else "clean"
        owner, repo = inst["repo"].split("/")
        saved = args.out / f"{iid}.json"
        record = json.loads(saved.read_text()) if saved.exists() else None
        if record is None:
            print(f"[{iid}] ({kind}) preparing", flush=True)
            head = inst["pr_commits"][-1]["sha"]
            pr = runner.PullRequest(
                url=f"https://github.com/{inst['repo']}",
                owner=owner,
                repo=repo,
                number=int(iid.rsplit("-", 1)[1]),
                title=inst["pr_title"],
                body=inst["pr_statement"] or "",
                merge_base=runner.merge_base(owner, repo, inst["base_commit"], head),
                head=head,
            )
            path = runner.prepare_repo(
                pr, args.work_dir.resolve() / iid, repo, enrich=not args.skip_enrich
            )
            if args.prepare_only:
                prompt = judge_prompt(inst, "<review goes here>", judge)
                print(f"[{iid}] ready at {path}; judge prompt {len(prompt)} chars", flush=True)
                continue
            print(f"[{iid}] reviewing in {path}", flush=True)
            review = runner.run_review(path, model=args.model, budget_usd=args.budget_usd)
            failed = runner.review_failed(review)
            if failed:
                print(f"[{iid}] review failed, not scored or saved: {failed}", flush=True)
                continue
            record = {
                "instance_id": iid,
                "change_introduced": inst["change_introduced"],
                "review": review,
            }
            saved.write_text(json.dumps(record, indent=2))
        if "verdict" not in record or args.rejudge:
            print(f"[{iid}] judging", flush=True)
            record["verdict"] = judge_review(
                inst, record["review"]["report"], judge, args.judge_model
            )
            saved.write_text(json.dumps(record, indent=2))
        records.append({**record, "instance": inst})

    if args.prepare_only:
        return
    for rec in records:
        v, r = rec["verdict"], rec["review"]
        kind = "change" if rec["instance"]["change_introduced"] else "clean"
        if "error" in v:
            print(f"  {rec['instance_id']:<36}{kind:<7} JUDGE ERROR")
            continue
        c = point_counts(rec["instance"], v)
        print(
            f"  {rec['instance_id']:<36}{kind:<7} flagged={flagged(v)!s:<6}"
            f"tp={c['tp']} fp={c['fp']} fn={c['fn']}  review ${r['cost_usd'] or 0:.2f}"
            f" {r['duration_s']:.0f}s  judge ${v['judge_cost_usd']:.2f}"
        )
        if "phases" in r:
            print(f"    phases {r['phases']}")
    summary = summarize(records)
    print(
        f"\n{summary['scored']} PRs scored ({summary['judge_errors']} judge errors), "
        f"judge {args.judge_model}"
    )
    for name in ("pr_level", "point_level", "functional_points"):
        m = summary[name]
        extra = f"  acc {m['accuracy']:.0%}" if "accuracy" in m else ""
        print(
            f"  {name:<18} P {m['precision']:.0%}  R {m['recall']:.0%}  F1 {m['f1']:.0%}"
            f"  (tp {m['tp']} fp {m['fp']} fn {m['fn']}){extra}"
        )
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
