"""Tests for the review-prep diff trimmer."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from klaussy.cli import app
from klaussy.review_prep import (
    PARALLEL_THRESHOLD,
    Decision,
    ReviewPayload,
    classify,
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
    assert pl.lenses == ["correctness", "correctness-2", "architecture", "security", "scope"]
    md = render_markdown(pl, summary_only=True)
    assert "**Launch these 5 lens sub-agents in one message**" in md
    assert "- security → `lens-security.md`" in md
    assert "This is the second correctness pass." in md
    assert render_dict(pl)["lenses"] == pl.lenses


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
