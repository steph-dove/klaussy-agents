"""Tests for the deterministic verbose-comment detector and its guard wiring."""

import importlib.util
from pathlib import Path

from klaussy import hooks as hooks_mod
from klaussy.comment_lint import COMMENT_RUN_MAX, COMMENT_WORD_MAX, analyze

TEMPLATES = Path(hooks_mod.__file__).parent / "templates" / "hooks"


# --- run-length heuristic --------------------------------------------------


def test_flags_consecutive_comment_block():
    src = (
        "x = 1\n"
        "# this function takes the user input and validates it\n"
        "# against the schema, then normalizes the casing because\n"
        "# downstream code assumes lowercase, and finally returns\n"
        "# the cleaned value to the caller for further processing\n"
        "y = 2\n"
    )
    findings = analyze("foo.py", src)
    assert len(findings) == 1
    assert findings[0].start == 2
    assert findings[0].end == 5
    assert "4 lines" in findings[0].detail


def test_short_block_under_threshold_is_clean():
    src = "# one\n# two\n# three\nx = 1\n"
    assert COMMENT_RUN_MAX == 4
    assert analyze("foo.py", src) == []


def test_blank_line_breaks_the_run():
    src = "x = 0\n# one\n# two\n\n# three\n# four\nx = 1\n"
    # two runs of 2 — neither reaches the threshold
    assert analyze("foo.py", src) == []


# --- word-count heuristic --------------------------------------------------


def test_flags_single_overlong_comment():
    long = " ".join(["word"] * (COMMENT_WORD_MAX + 5))
    findings = analyze("foo.py", f"x = 1  # {long}\n")
    assert len(findings) == 1
    assert findings[0].detail == f"{COMMENT_WORD_MAX + 5} words"


def test_short_inline_comment_is_clean():
    assert analyze("foo.py", "x = 1  # bump the counter\n") == []


# --- exemptions ------------------------------------------------------------


def test_docstring_is_not_a_comment():
    src = (
        "def f():\n"
        '    """This is a long docstring that goes well beyond the word budget '
        "to make sure docstrings are never treated as comment prose by the "
        'detector no matter how many words they contain at all."""\n'
        "    return 1\n"
    )
    assert analyze("foo.py", src) == []


def test_directive_block_is_exempt():
    src = (
        "x = 1  # noqa: E501\n"
        "# type: ignore\n"
        "# pyright: reportMissingImports=false\n"
        "# ruff: noqa\n"
        "# mypy: ignore-errors\n"
    )
    assert analyze("foo.py", src) == []


def test_license_header_block_is_exempt():
    header = "\n".join(f"# license line {i} with several descriptive words here" for i in range(8))
    src = f"{header}\nimport os\n"
    assert analyze("foo.py", src) == []


def test_shebang_then_code_is_clean():
    src = "#!/usr/bin/env python3\nimport sys\n"
    assert analyze("foo.py", src) == []


def test_hash_inside_string_is_not_a_comment():
    long = " ".join(["word"] * (COMMENT_WORD_MAX + 5))
    src = f'url = "# {long}"\n'
    assert analyze("foo.py", src) == []


def test_bare_url_comment_is_exempt():
    src = "# https://example.com/some/very/long/path/that/has/many/segments/in/it\nx = 1\n"
    assert analyze("foo.py", src) == []


# --- C-style languages -----------------------------------------------------


def test_flags_js_slash_block():
    src = (
        "const x = 1;\n"
        "// first line of a long narration block describing the code\n"
        "// second line continuing the explanation for the reader here\n"
        "// third line still going on about the implementation details\n"
        "// fourth line that finally wraps up this verbose commentary\n"
    )
    findings = analyze("app.js", src)
    assert len(findings) == 1
    assert "4 lines" in findings[0].detail


def test_jsdoc_block_is_exempt():
    src = (
        "/**\n"
        " * line one of the doc\n"
        " * line two of the doc\n"
        " * line three of the doc\n"
        " * line four of the doc\n"
        " */\n"
        "function f() {}\n"
    )
    assert analyze("app.ts", src) == []


def test_inline_slash_url_not_flagged():
    long = " ".join(["word"] * (COMMENT_WORD_MAX + 5))
    src = f"const u = compute();  // see http://example.com {long}\n"
    # inline // is intentionally ignored, so the http:// trap can't trip
    assert analyze("app.js", src) == []


def test_block_comment_over_threshold_flagged():
    src = (
        "y := 0\n"  # code first, so the block isn't a top-of-file header
        "/*\n"
        "one line of narration in a block comment here for testing\n"
        "two lines of narration in a block comment here for testing\n"
        "three lines of narration in a block comment for testing it\n"
        "four lines of narration in a block comment for testing now\n"
        "*/\n"
        "x()\n"
    )
    findings = analyze("app.go", src)
    assert findings and "lines" in findings[0].detail


# --- misc ------------------------------------------------------------------


def test_unsupported_extension_returns_empty():
    assert analyze("notes.md", "# a markdown heading\n# another heading\n") == []


def test_render_format_single_and_range():
    src = (
        "x = 1\n"
        "# aaa bbb ccc ddd eee fff ggg hhh\n"
        "# iii jjj kkk lll mmm nnn ooo ppp\n"
        "# qqq rrr sss ttt uuu vvv www xxx\n"
        "# yyy zzz aaa bbb ccc ddd eee fff\n"
    )
    rendered = analyze("foo.py", src)[0].render()
    assert rendered.startswith("foo.py:2-5: verbose comment (4 lines)")
    assert "strip to the bare minimum" in rendered


# --- guard wiring ----------------------------------------------------------


def _load_guard(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, TEMPLATES / relpath)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_commit_guards_run_the_verbose_check():
    for relpath, name in (
        ("git_commit_guard.py", "_claude_commit_guard"),
        ("multi/commit_guard.py", "_multi_commit_guard"),
    ):
        mod = _load_guard(relpath, name)
        assert mod.VERBOSE_COMMENT_CMD == "klaussy comment-lint __KLAUSSY_PATHS__"
        # PATHS placeholder resolves to the staged files, like the other checks.
        resolved = mod._resolve(mod.VERBOSE_COMMENT_CMD, ["a.py", "b.py"])
        assert resolved == "klaussy comment-lint a.py b.py"
