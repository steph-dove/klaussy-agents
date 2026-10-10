import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks"))

import label_fps  # noqa: E402
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
        "subagents_incomplete": 0,
        "validation_rubric_read": True,
        "hunk_sweep_read": False,
    }


def _agent_call(tool_id: str, description: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Agent",
                    "input": {"description": description, "prompt": "claims"},
                }
            ]
        },
    }


def _launched(tool_id: str) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "Async agent launched successfully.\nagentId: abc (internal)",
                }
            ]
        },
    }


def test_parse_stream_reads_background_agents_from_task_events():
    events = [
        _agent_call("t1", "Validate F1-F3"),
        {"type": "system", "subtype": "task_started", "tool_use_id": "t1", "is_backgrounded": True},
        _launched("t1"),
        {"type": "result", "total_cost_usd": 0.5},
        {
            "type": "system",
            "subtype": "task_notification",
            "tool_use_id": "t1",
            "status": "completed",
            "summary": "F1 · KEEP · x",
        },
        {"type": "result", "total_cost_usd": 1.25},
    ]
    trace, result = runner._parse_stream("\n".join(json.dumps(e) for e in events))
    assert trace[0]["output"] == "F1 · KEEP · x" and trace[0]["status"] == "completed"
    assert result["costs"] == [0.5, 1.25]


def test_review_phases_count_agents_that_never_finished():
    events = [
        _agent_call("t1", "Correctness lens"),
        {"type": "system", "subtype": "task_started", "tool_use_id": "t1", "is_backgrounded": True},
        _launched("t1"),
        _agent_call("t2", "Validate F1-F4"),
        {"type": "system", "subtype": "task_started", "tool_use_id": "t2", "is_backgrounded": True},
        _launched("t2"),
        {
            "type": "system",
            "subtype": "task_notification",
            "tool_use_id": "t1",
            "status": "completed",
        },
        {"type": "system", "subtype": "task_notification", "tool_use_id": "t2", "status": "killed"},
    ]
    trace, _ = runner._parse_stream("\n".join(json.dumps(e) for e in events))
    assert runner.review_phases(trace)["subagents_incomplete"] == 1


def test_review_phases_count_skill_files_read_from_the_shell():
    trace = [
        {"tool": "Bash", "detail": "cat ../.claude/skills/x-review/lens-validation.md | head"},
        {"tool": "Read", "detail": "/r/.claude/skills/x-review/lens-correctness.md"},
    ]
    phases = runner.review_phases(trace)
    assert phases["validation_rubric_read"] and phases["hunk_sweep_read"]
    assert not phases["parallel_path"]


def test_review_failed_rejects_errors_and_missing_reports():
    assert runner.review_failed({"error": "budget exceeded", "report_written": True})
    assert runner.review_failed({"error": False, "report_written": False})
    assert runner.review_failed({"error": None, "report_written": True}) is None


PROMPTS = {"JUDGE_PROMPT": "{golden_comment}|{candidate}"}


def test_judge_takes_the_majority_vote(monkeypatch):
    answers = iter([True, False, True])
    monkeypatch.setattr(
        runner,
        "ask_claude_json",
        lambda system, prompt, model: {"match": next(answers), "confidence": 0.9, "_cost_usd": 0},
    )
    golden = [{"comment": "g", "category": "bug"}]
    result = martian.judge(golden, ["c"], [[0]], PROMPTS, "m", samples=3)
    assert result["true_positives"][0]["votes"] == "2/3"
    assert result["false_positives"] == []


def test_judge_does_not_count_a_matched_duplicate_as_false_positive(monkeypatch):
    monkeypatch.setattr(
        runner,
        "ask_claude_json",
        lambda system, prompt, model: {
            "match": prompt.endswith("|a"),
            "confidence": 0.8,
            "_cost_usd": 0,
        },
    )
    golden = [{"comment": "g", "category": "bug"}]
    result = martian.judge(golden, ["a", "a again", "b"], [[0, 1], [2]], PROMPTS, "m", samples=1)
    assert result["false_positives"] == ["b"]


def test_judge_leaves_pairs_without_a_majority_unscored(monkeypatch):
    def flaky(system, prompt, model):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(runner, "ask_claude_json", flaky)
    golden = [{"comment": "g", "category": "bug"}]
    result = martian.judge(golden, ["c"], [[0]], PROMPTS, "m", samples=3)
    assert result["judge_errors"] == 1
    assert "rate limited" in result["judge_error_samples"][0]


def test_severe_only_keeps_medium_and_above():
    kept = martian.severe_only(REPORT)
    assert kept.startswith("High · Correctness · `pkg/a.go:12`")
    assert "Rename x" not in kept


def test_load_constants_reads_literals_without_importing(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text('import nonexistent_module\nPROMPT = "x {a}"\nOTHER = 1\n')
    assert runner.load_constants(src, {"PROMPT"}) == {"PROMPT": "x {a}"}
    with pytest.raises(SystemExit):
        runner.load_constants(src, {"MISSING"})


def test_extract_rejects_a_response_without_an_issues_list(monkeypatch):
    monkeypatch.setattr(
        runner, "ask_claude_json", lambda system, prompt, model: {"oops": 1, "_cost_usd": 0}
    )
    with pytest.raises(ValueError):
        martian.extract("x" * 40, {"EXTRACT_PROMPT": "{comment}"}, "m")


def test_dedup_flags_a_fallback_when_groups_miss_a_candidate(monkeypatch):
    monkeypatch.setattr(
        runner,
        "ask_claude_json",
        lambda system, prompt, model: {"groups": [[0, 1]], "_cost_usd": 0},
    )
    groups, _, fell_back = martian.dedup(["a", "b", "c"], {"STRICT_PROMPT": "{candidates}"}, "m")
    assert fell_back and groups == [[0], [1], [2]]


def test_run_review_resumes_a_session_that_ended_without_a_report(tmp_path, monkeypatch):
    repo = tmp_path / "shop"
    (repo / ".git").mkdir(parents=True)
    calls = []

    def fake_claude(cmd, **kwargs):
        calls.append(cmd)
        if "--resume" in cmd:
            (repo / "REVIEW_OUTPUT.md").write_text("**High · Correctness · `a.py:1`**\n\nFix.\n")
        result = {"type": "result", "subtype": "success", "session_id": "s1"}
        result["total_cost_usd"] = 1.0
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(result), stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_claude)
    review = runner.run_review(repo)
    assert review["report_written"] and review["resumes"] == 1
    assert calls[1][calls[1].index("--resume") + 1] == "s1"
    assert review["cost_usd"] == 2.0


def test_prepare_repo_rerenders_skills_in_a_reused_checkout(tmp_path, monkeypatch):
    dest = tmp_path / "shop"
    (dest / ".claude" / "skills" / "shop-review").mkdir(parents=True)
    (dest / ".claude" / "skills" / "shop-review" / "SKILL.md").write_text("old")
    (dest / "REVIEW_OUTPUT.md").write_text("stale")
    calls = []
    monkeypatch.setattr(runner, "_run", lambda args, **kw: calls.append(args) or "")
    pr = runner.PullRequest("url", "o", "shop", 1, "t", "b", "base", "head")
    assert runner.prepare_repo(pr, tmp_path, "shop") == dest
    assert calls == [
        ["klaussy", "skills", "--repo", str(dest), "-b", "main", "--agents", "claude", "--force"]
    ]
    assert not (dest / "REVIEW_OUTPUT.md").exists()


def test_run_review_does_not_resume_a_failed_run(tmp_path, monkeypatch):
    repo = tmp_path / "shop"
    (repo / ".git").mkdir(parents=True)
    result = {"type": "result", "subtype": "error_max_budget_usd", "session_id": "s1"}
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(result), ""),
    )
    review = runner.run_review(repo)
    assert review["resumes"] == 0 and review["error"] == "error_max_budget_usd"


def test_parse_stream_skips_events_it_does_not_recognize():
    events = [
        {"type": "system", "message": "compacting context"},
        {"type": "assistant", "message": {"content": "plain text"}},
        [1, 2],
        {"type": "result", "total_cost_usd": 0.5},
    ]
    trace, result = runner._parse_stream("\n".join(json.dumps(e) for e in events))
    assert trace == [] and result["total_cost_usd"] == 0.5


def test_label_fps_rejects_an_unknown_label(monkeypatch):
    monkeypatch.setattr(
        runner, "ask_claude_json", lambda s, p, m: {"label": "maybe", "_cost_usd": 0}
    )
    with pytest.raises(ValueError):
        label_fps.label("finding", ["golden"], "diff", "m")
    monkeypatch.setattr(
        runner, "ask_claude_json", lambda s, p, m: {"label": "real", "reason": "r", "_cost_usd": 0}
    )
    assert label_fps.label("finding", [], "x" * 90_000, "m")["label"] == "real"


def test_label_fps_reads_swr_unmatched_predictions():
    verdict = {
        "pred_points": [
            {"id": "P1", "description": "matched"},
            {"id": "P2", "description": "extra"},
        ],
        "gt_points": [{"description": "expected", "hit": "YES", "hit_by": "P1"}],
    }
    change = {"verdict": verdict, "change_introduced": True}
    assert label_fps.swr_false_positives(change) == (["expected"], ["extra"])
    clean = {"verdict": verdict, "change_introduced": False}
    assert label_fps.swr_false_positives(clean) == ([], ["matched", "extra"])
    assert label_fps.swr_false_positives({"verdict": {"error": "x"}}) is None


def test_swr_main_keeps_going_when_one_instance_fails(tmp_path, monkeypatch, capsys):
    rows = [{"instance_id": "a-1"}, {"instance_id": "b-2"}]
    seen = []

    def run_instance(inst, args, judge):
        seen.append(inst["instance_id"])
        if inst["instance_id"] == "a-1":
            raise RuntimeError("clone failed")

    monkeypatch.setattr(swrbench, "load_dataset", lambda d: rows)
    monkeypatch.setattr(swrbench, "load_judge", lambda d: {})
    monkeypatch.setattr(swrbench, "run_instance", run_instance)
    argv = ["swrbench", "--swr-dir", str(tmp_path), "--out", str(tmp_path / "out")]
    argv += ["--ids", "a-1", "b-2", "--prepare-only", "--skip-enrich", "--workers", "2"]
    monkeypatch.setattr(sys, "argv", argv)
    swrbench.main()
    assert sorted(seen) == ["a-1", "b-2"]
    out = capsys.readouterr().out
    assert "[a-1] failed, not scored: RuntimeError: clone failed" in out
    assert "Not scored (1): a-1" in out
