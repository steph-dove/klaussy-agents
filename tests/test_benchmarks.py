import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks"))

import martian  # noqa: E402
import runner  # noqa: E402
import swrbench  # noqa: E402

REPORT = """\
**High · Correctness · `pkg/a.go:12`**

The lock is released before the write. Hold it.

**Nit · Readability · `pkg/b.go:3`**

Rename x.

**Verdict:** Request Changes · reviewed at `abc123`
"""


def test_parse_findings_splits_on_metadata_lines():
    findings = runner.parse_findings(REPORT)
    assert [f["severity"] for f in findings] == ["High", "Nit"]
    assert findings[0]["location"] == "pkg/a.go:12"
    assert findings[0]["text"].endswith("Hold it.")
    assert "Verdict" not in findings[1]["text"]


def test_parse_findings_empty_report():
    assert runner.parse_findings("**Verdict:** Approve") == []


def test_profile_counts_exclude_out_of_profile_matches():
    evaluation = {
        "true_positives": [{"category": "bug"}, {"category": "style"}],
        "false_negatives": [{"category": "style"}, {"category": "perf"}],
        "false_positives": ["a", "b"],
    }
    assert martian.profile_counts(evaluation, martian.PROFILES["strict"]) == {
        "tp": 1,
        "fp": 2,
        "fn": 0,
    }
    assert martian.profile_counts(evaluation, martian.PROFILES["all"]) == {
        "tp": 2,
        "fp": 2,
        "fn": 2,
    }


def test_prf1():
    m = runner.prf1(tp=2, fp=2, fn=2)
    assert m["precision"] == m["recall"] == m["f1"] == m["f2"] == 0.5
    assert runner.prf1(tp=0, fp=0, fn=0)["f1"] == 0.0


CHANGE = {"change_introduced": True, "changes": [{"change_type": "F.2 Logic"}] * 2}
CLEAN = {"change_introduced": False, "changes": []}


def _verdict(good, preds, hits=()):
    return {
        "identified_as_good": good,
        "pred_points": [{"id": f"PRED-POINT-{i}", "change_category": c} for i, c in preds],
        "gt_points": [
            {"change_category": "F.2", "hit": "YES" if h else "NO", "hit_by": h or "N/A"}
            for h in hits
        ],
    }


def test_swr_point_counts_change_pr():
    v = _verdict("NO", [(1, "F.2"), (2, "E.3.1")], hits=("PRED-POINT-1", None))
    assert swrbench.point_counts(CHANGE, v) == {"tp": 1, "fp": 1, "fn": 1}
    assert swrbench.point_counts(CHANGE, v, "F") == {"tp": 1, "fp": 0, "fn": 1}


def test_swr_every_point_on_clean_pr_is_false_positive():
    v = _verdict("NO", [(1, "F.2"), (2, "E.1.1")])
    assert swrbench.point_counts(CLEAN, v) == {"tp": 0, "fp": 2, "fn": 0}


def test_swr_summary_pr_level():
    records = [
        {"instance": CHANGE, "verdict": _verdict("NO", [(1, "F.2")], ("PRED-POINT-1", None))},
        {"instance": CLEAN, "verdict": _verdict("YES", [(1, "E.1.1")])},
        {"instance": CLEAN, "verdict": _verdict("NO", [(1, "F.2")])},
        {"instance": CLEAN, "verdict": {"error": "x"}},
    ]
    s = swrbench.summarize(records)
    assert s["judge_errors"] == 1
    assert {k: s["pr_level"][k] for k in ("tp", "fp", "fn", "tn")} == {
        "tp": 1,
        "fp": 1,
        "fn": 0,
        "tn": 1,
    }
    assert s["point_level"]["fp"] == 2


def test_swr_valid_verdict_needs_every_ground_truth_point():
    v = _verdict("NO", [], hits=("PRED-POINT-1",))
    assert not swrbench.valid_verdict(v, CHANGE)
    assert swrbench.valid_verdict(_verdict("YES", []), CLEAN)


def test_parse_stream_records_subagent_calls_and_phases():
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "shop-review"}},
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "klaussy review-prep"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/r/.claude/skills/shop-review/parallel.md"},
                    },
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Agent",
                        "input": {"description": "validate batch 1", "prompt": "check these"},
                    },
                ]
            },
        },
        {
            "type": "assistant",
            "parent_tool_use_id": "t1",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/r/.claude/skills/shop-review/lens-validation.md"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [{"type": "text", "text": "1 finding survives"}],
                    }
                ]
            },
        },
        {"type": "result", "total_cost_usd": 1.5, "num_turns": 7},
        "not json",
    ]
    stdout = "\n".join(e if isinstance(e, str) else json.dumps(e) for e in events)
    trace, result = runner._parse_stream(stdout)
    assert result["total_cost_usd"] == 1.5
    assert trace[-1]["subagent"] and not trace[0]["subagent"]
    agent = next(t for t in trace if t["tool"] == "Agent")
    assert agent["prompt"] == "check these" and agent["output"] == "1 finding survives"
    assert runner.review_phases(trace) == {
        "skill_invoked": True,
        "review_prep": True,
        "read_claude_md": False,
        "parallel_path": True,
        "subagents": 1,
        "validation_rubric_read": True,
    }


def test_parse_stream_matches_background_agent_output_by_id():
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t9",
                        "name": "Agent",
                        "input": {"description": "Validate F1-F3", "prompt": "claims"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t9",
                        "content": "Async agent launched successfully.\nagentId: abc123 (internal)",
                    }
                ]
            },
        },
        {"type": "result", "total_cost_usd": 0.5},
        {
            "type": "user",
            "message": {"content": "<task-notification>abc123: F1 · KEEP · x</task-notification>"},
        },
        {"type": "result", "total_cost_usd": 1.25},
    ]
    trace, result = runner._parse_stream("\n".join(json.dumps(e) for e in events))
    assert "F1 · KEEP" in trace[0]["output"]
    assert "launched" not in trace[0]["output"]
    assert result["costs"] == [0.5, 1.25]


def test_review_failed_rejects_errors_and_missing_reports():
    assert runner.review_failed({"error": "budget exceeded", "report_written": True})
    assert runner.review_failed({"error": False, "report_written": False})
    assert runner.review_failed({"error": None, "report_written": True}) is None
