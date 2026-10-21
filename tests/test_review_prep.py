"""Tests for the review-prep diff trimmer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from klaussy.cli import app
from klaussy.review_prep import (
    PARALLEL_THRESHOLD,
    Decision,
    ReviewPayload,
    _elide_long_lines,
    classify,
    plan_chunks,
    prepare_review,
    render_dict,
    render_markdown,
    split_file_diffs,
)

# A multi-file unified diff covering: a real source file, a lockfile, a vendored
# tree, a minified asset, a binary, and a pure rename.
SAMPLE_DIFF = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 def run():
-    return 1
+    return 2
+    # changed
diff --git a/package-lock.json b/package-lock.json
index 3333333..4444444 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,5 +1,5 @@
-  "old": 1
+  "new": 2
diff --git a/node_modules/leftpad/index.js b/node_modules/leftpad/index.js
index 5555555..6666666 100644
--- a/node_modules/leftpad/index.js
+++ b/node_modules/leftpad/index.js
@@ -1 +1 @@
-module.exports = 1
+module.exports = 2
diff --git a/static/app.min.js b/static/app.min.js
index 7777777..8888888 100644
--- a/static/app.min.js
+++ b/static/app.min.js
@@ -1 +1 @@
-var a=1
+var a=2
diff --git a/assets/logo.png b/assets/logo.png
index 9999999..aaaaaaa 100644
Binary files a/assets/logo.png and b/assets/logo.png differ
diff --git a/src/old_name.py b/src/new_name.py
similarity index 100%
rename from src/old_name.py
rename to src/new_name.py
"""


def test_split_finds_every_file():
    files = split_file_diffs(SAMPLE_DIFF)
    paths = [f.path for f in files]
    assert paths == [
        "src/app.py",
        "package-lock.json",
        "node_modules/leftpad/index.js",
        "static/app.min.js",
        "assets/logo.png",
        "src/new_name.py",
    ]


def test_counts_added_removed():
    app = next(f for f in split_file_diffs(SAMPLE_DIFF) if f.path == "src/app.py")
    assert (app.added, app.removed) == (2, 1)


def test_classification_reasons():
    by_path = {f.path: classify(f) for f in split_file_diffs(SAMPLE_DIFF)}
    assert by_path["src/app.py"] == (True, "reviewable")
    assert by_path["package-lock.json"][0] is False
    assert by_path["package-lock.json"][1] == "lockfile"
    assert by_path["node_modules/leftpad/index.js"][0] is False
    assert "node_modules" in by_path["node_modules/leftpad/index.js"][1]
    assert by_path["static/app.min.js"] == (False, "minified/sourcemap")
    assert by_path["assets/logo.png"] == (False, "binary")
    assert by_path["src/new_name.py"][0] is False  # pure rename, no hunks


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg)


def test_prepare_review_keeps_source_drops_noise(tmp_path: Path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    _commit_file(tmp_path, "src/app.py", "def run():\n    return 1\n", "init")
    _git(tmp_path, "branch", "-M", "main")
    _git(tmp_path, "checkout", "-b", "feature")
    # One real change + one lockfile change on the branch.
    (tmp_path / "src/app.py").write_text("def run():\n    return 2\n")
    (tmp_path / "package-lock.json").write_text('{"a": 2}\n')
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "work")

    payload = prepare_review(repo=tmp_path, base_branch="main")
    kept = {d.path for d in payload.kept}
    dropped = {d.path for d in payload.dropped}
    assert "src/app.py" in kept
    assert "package-lock.json" in dropped
    assert "package-lock.json" not in payload.trimmed_diff
    assert "src/app.py" in payload.trimmed_diff


def _repo_with_stale_local_main(repo: Path) -> None:
    """`main` stays at the first commit; origin/main has a merged change the branch is cut from."""
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _commit_file(repo, "src/app.py", "def run():\n    return 1\n", "init")
    _git(repo, "checkout", "-b", "upstream")
    _commit_file(repo, "src/merged.py", "MERGED = 1\n", "merged upstream")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "checkout", "-b", "feature")
    _git(repo, "branch", "-D", "upstream")
    _commit_file(repo, "src/feature.py", "FEATURE = 1\n", "work")


def test_a_diff_with_non_utf8_bytes_still_prepares(tmp_path: Path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    _commit_file(tmp_path, "src/app.py", "def run():\n    return 1\n", "init")
    _git(tmp_path, "branch", "-M", "main")
    _git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "src/app.py").write_text("def run():\n    return 2\n")
    # Latin-1 text with no NUL byte, so git diffs it as text rather than binary.
    (tmp_path / "notes.txt").write_bytes(b"caf\xe9 \x89PNG header-ish\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "work")

    payload = prepare_review(repo=tmp_path, base_branch="main")
    assert "src/app.py" in {d.path for d in payload.kept}
    assert "�" in payload.trimmed_diff


def test_a_stale_local_main_leaves_merged_commits_out_of_the_diff(tmp_path: Path):
    _repo_with_stale_local_main(tmp_path)
    paths = {d.path for d in prepare_review(repo=tmp_path).decisions}
    assert paths == {"src/feature.py"}


def test_a_given_base_is_used_as_is(tmp_path: Path, monkeypatch):
    """The ReviewBench agent points local main at the fork point on purpose; origin/main may
    already hold the merged PR, which would empty the diff."""
    _repo_with_stale_local_main(tmp_path)
    both = {"src/merged.py", "src/feature.py"}
    assert {d.path for d in prepare_review(repo=tmp_path, base_branch="main").decisions} == both
    monkeypatch.setenv("KLAUSSY_REVIEW_BASE", "main")
    assert {d.path for d in prepare_review(repo=tmp_path).decisions} == both


def test_render_markdown_has_manifest_and_summary():
    from klaussy.review_prep import Decision, ReviewPayload

    pl = ReviewPayload(
        decisions=[
            Decision("src/app.py", True, "reviewable", 2, 1),
            Decision("package-lock.json", False, "lockfile", 50, 40),
        ],
        trimmed_diff="diff --git a/src/app.py b/src/app.py\n+x\n",
    )
    md = render_markdown(pl)
    assert "## Reviewable diff" in md
    assert "## Excluded from review (1 file(s))" in md
    assert "`package-lock.json` — lockfile" in md
    assert "review-prep:" in md  # summary comment
    d = render_dict(pl)
    assert d["dropped_lines"] == 90 and d["kept_lines"] == 3


def _payload(kept_lines: int):
    return ReviewPayload(
        decisions=[Decision("src/app.py", True, "reviewable", kept_lines, 0)],
        trimmed_diff="diff --git a/src/app.py b/src/app.py\n+x\n",
    )


def test_review_path_switches_to_parallel_at_threshold():
    assert _payload(PARALLEL_THRESHOLD - 1).path == "small"
    assert _payload(PARALLEL_THRESHOLD).path == "parallel"
    assert "**Review path: parallel** (150 reviewable lines ≥ 150)" in render_markdown(
        _payload(PARALLEL_THRESHOLD)
    )
    assert render_dict(_payload(10))["path"] == "small"


def test_summary_lists_files_without_the_diff():
    md = render_markdown(_payload(3), summary_only=True)
    assert "**Review path: small**" in md
    assert "- `src/app.py` (+3 / -0)" in md
    assert "## Reviewable diff" not in md and "+x" not in md


def test_forced_path_overrides_size():
    pl = ReviewPayload(
        decisions=[Decision("src/app.py", True, "reviewable", 3, 0)],
        trimmed_diff="",
        forced_path="parallel",
    )
    assert pl.path == "parallel"
    assert "**Review path: parallel** (set by --path; 3 reviewable lines)" in render_markdown(pl)


def test_cli_rejects_unknown_path(tmp_path: Path):
    result = CliRunner().invoke(app, ["review-prep", "--repo", str(tmp_path), "--path", "big"])
    assert result.exit_code != 0
    assert "small or parallel" in result.output


def _file(path: str, added: list[str]) -> str:
    body = "".join(f"+{line}\n" for line in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n{body}"


def _parallel(*files: str) -> ReviewPayload:
    return ReviewPayload(
        decisions=[Decision("src/app.py", True, "reviewable", PARALLEL_THRESHOLD, 0)],
        trimmed_diff="".join(files),
    )


def test_parallel_path_lists_the_base_lenses():
    pl = _parallel(_file("src/app.py", ["x = 1"]))
    assert pl.lenses == [
        "correctness",
        "correctness-2",
        "architecture",
        "security",
        "scope",
        "docs",
        "tests",
    ]
    md = render_markdown(pl, summary_only=True)
    assert "**Launch these 7 lens sub-agents in one message**" in md
    assert "- security → `lens-security.md`" in md
    assert "This is the second correctness pass." in md
    assert render_dict(pl)["lenses"] == pl.lenses


def test_accessibility_lens_runs_only_when_ui_changes():
    assert "accessibility" in _parallel(_file("web/src/Button.tsx", ["x"])).lenses
    assert "accessibility" in _parallel(_file("static/site.css", ["a {}"])).lenses
    assert "accessibility" not in _parallel(_file("src/app.py", ["x = 1"])).lenses


def test_agentic_lens_on_skill_paths_and_llm_imports():
    assert "agentic" in _parallel(_file(".claude/skills/x/SKILL.md", ["hi"])).lenses
    assert "agentic" in _parallel(_file("src/bot.py", ["import anthropic"])).lenses
    assert "agentic" in _parallel(_file("src/bot.ts", ['import OpenAI from "openai"'])).lenses
    assert "agentic" not in _parallel(_file("src/app.py", ["import os"])).lenses


def test_design_docs_add_the_adr_lens_or_a_small_path_note():
    adr = _file("docs/adr/0007-queues.md", ["# Use queues"])
    nygard = _file("notes/plan.md", ["## Status", "## Context", "## Decision"])
    plain = _file("README.md", ["## Status", "words"])
    pl = _parallel(adr, nygard, plain)
    assert pl.design_docs == ["docs/adr/0007-queues.md", "notes/plan.md"]
    assert pl.lenses[-1] == "adr"
    assert "(design docs: docs/adr/0007-queues.md, notes/plan.md)" in render_markdown(pl)

    small = ReviewPayload(
        decisions=[Decision("docs/adr/0007-queues.md", True, "reviewable", 3, 0)],
        trimmed_diff=adr,
    )
    assert small.lenses == []
    assert "**Design docs changed:** docs/adr/0007-queues.md" in render_markdown(small)


def _file_diff(path: str, added_lines: int, width: int = 60) -> str:
    body = "".join(f"+{'x' * width} {i}\n" for i in range(added_lines))
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
        f"@@ -0,0 +1,{added_lines} @@\n{body}"
    )


def test_a_small_diff_has_no_chunks():
    payload = ReviewPayload(decisions=[], trimmed_diff=_file_diff("src/a.py", 10))
    assert payload.chunk_plan is None
    assert "## Reviewable diff" in render_markdown(payload)


def test_plan_chunks_puts_code_before_tests_and_docs_and_respects_the_limit():
    files = split_file_diffs(
        _file_diff("docs/guide.md", 50)
        + _file_diff("tests/test_a.py", 50)
        + _file_diff("src/b.py", 50)
        + _file_diff("src/a.py", 50)
    )
    plan = plan_chunks(files, limit=4_000, max_chunks=10)
    order = [p for c in plan.chunks for p in c.paths]
    assert order == ["src/a.py", "src/b.py", "tests/test_a.py", "docs/guide.md"]
    assert all(len(c.text) <= 4_000 for c in plan.chunks)
    assert not plan.unreviewed


def test_plan_chunks_lists_what_the_budget_left_out():
    files = split_file_diffs(_file_diff("src/a.py", 50) + _file_diff("docs/b.md", 50))
    plan = plan_chunks(files, limit=4_000, max_chunks=1)
    assert [p for c in plan.chunks for p in c.paths] == ["src/a.py"]
    assert plan.unreviewed == ["docs/b.md"]


def test_a_hunk_too_big_for_one_chunk_splits_with_matching_line_numbers():
    [fd] = split_file_diffs(_file_diff("src/big.py", 300))
    plan = plan_chunks([fd], limit=6_000)
    headers = [
        ln for c in plan.chunks for ln in c.text.splitlines() if ln.startswith("@@ ")
    ]
    assert len(plan.chunks) > 1 and all(len(c.text) <= 6_000 for c in plan.chunks)
    starts = [int(h.split("+")[1].split(",")[0]) for h in headers]
    counts = [int(h.split(",")[-1].split(" ")[0]) for h in headers]
    assert starts[0] == 1
    assert all(starts[i + 1] == starts[i] + counts[i] for i in range(len(starts) - 1))
    assert sum(counts) == 300


def test_a_file_with_a_huge_line_is_classified_minified():
    [fd] = split_file_diffs(_file_diff("lib/mime.js", 2, width=6_000))
    assert classify(fd)[0] is False
    assert "minified" in classify(fd)[1]


def test_one_huge_line_is_elided_and_the_rest_of_the_file_kept():
    diff = (
        "diff --git a/tests/test_x.py b/tests/test_x.py\n--- a/tests/test_x.py\n"
        "+++ b/tests/test_x.py\n@@ -0,0 +1,2 @@\n"
        f"+FIXTURE = '{'x' * 6_000}'\n+assert check(FIXTURE)\n"
    )
    [fd] = split_file_diffs(diff)
    assert classify(fd) == (True, "reviewable")
    body, elided = _elide_long_lines(fd.body)
    assert elided == 1
    assert "+assert check(FIXTURE)\n" in body and "x" * 6_000 not in body
    assert body.count("\n") == fd.body.count("\n")


def test_hunk_splitting_keeps_form_feeds_and_line_separators_inside_their_line():
    lines = [f"+line {i}\x0c\u2028 tail\n" for i in range(300)]
    diff = (
        "diff --git a/src/a.c b/src/a.c\n--- /dev/null\n+++ b/src/a.c\n"
        f"@@ -0,0 +1,300 @@\n{''.join(lines)}"
    )
    [fd] = split_file_diffs(diff)
    assert fd.added == 300
    plan = plan_chunks([fd], limit=4_000)
    headers = [ln for c in plan.chunks for ln in c.text.split("\n") if ln.startswith("@@ ")]
    assert sum(int(h.split(",")[-1].split(" ")[0]) for h in headers) == 300
    assert "".join(c.text for c in plan.chunks).count("tail") == 300


def test_a_chunked_diff_drops_the_second_correctness_pass_from_json_too():
    diff = "".join(_file_diff(f"src/m{i}.py", 200) for i in range(4))
    payload = ReviewPayload(
        decisions=[Decision("src/m0.py", True, "reviewable", PARALLEL_THRESHOLD, 0)],
        trimmed_diff=diff,
    )
    assert payload.chunk_plan is not None
    assert "correctness-2" not in payload.lenses
    assert render_dict(payload)["lenses"] == payload.lenses


def test_a_chunked_diff_prints_an_index_and_one_chunk_on_request():
    diff = "".join(_file_diff(f"src/m{i}.py", 200) for i in range(4))
    payload = ReviewPayload(decisions=[], trimmed_diff=diff, base_ref="origin/main")
    index = render_markdown(payload)
    assert "Too large to read at once" in index
    assert "klaussy review-prep --base origin/main --chunk <N>" in index
    assert "```diff" not in index
    first = render_markdown(payload, chunk=1)
    assert first.startswith("## Chunk 1 of") and "src/m0.py" in first
    with pytest.raises(ValueError, match="chunk must be"):
        render_markdown(payload, chunk=99)


def test_chunk_with_json_is_refused():
    result = CliRunner().invoke(app, ["review-prep", "--json", "--chunk", "1"])
    assert result.exit_code != 0
    assert "drop --json" in result.output
