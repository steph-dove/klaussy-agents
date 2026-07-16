"""Tests for the deterministic function-local import detector and its guard wiring."""

import importlib.util
from pathlib import Path

import pytest

from klaussy import hooks as hooks_mod
from klaussy.import_lint import analyze, scan_paths

TEMPLATES = Path(hooks_mod.__file__).parent / "templates" / "hooks"

# --- what counts as a local import -----------------------------------------


def test_top_level_imports_are_clean():
    src = "import json\nfrom pathlib import Path\n\n\ndef f():\n    return json, Path\n"
    assert analyze("m.py", src) == []


def test_flags_import_inside_function():
    findings = analyze("m.py", "def to_json():\n    import json\n    return json\n")
    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].statement == "import json"
    assert findings[0].scope == "to_json"


def test_flags_import_inside_method():
    src = "class C:\n    def m(self):\n        from x import y\n        return y\n"
    findings = analyze("m.py", src)
    assert len(findings) == 1
    assert findings[0].scope == "m"
    assert findings[0].statement == "from x import y"


def test_flags_import_inside_nested_function():
    src = "def outer():\n    def inner():\n        import os\n        return os\n    return inner\n"
    findings = analyze("m.py", src)
    assert len(findings) == 1
    assert findings[0].scope == "inner"


def test_flags_relative_import():
    findings = analyze("m.py", "def f():\n    from . import sibling\n    return sibling\n")
    assert len(findings) == 1
    assert findings[0].statement == "from . import sibling"


# --- exemptions -------------------------------------------------------------


def test_type_checking_block_is_top_level():
    """An `if TYPE_CHECKING:` guard is module scope, not a function."""
    src = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from x import Y\n"
    assert analyze("m.py", src) == []


def test_try_except_import_is_top_level():
    """The optional-dependency idiom at module level is not a local import."""
    src = "try:\n    import ujson as json\nexcept ImportError:\n    import json\n"
    assert analyze("m.py", src) == []


def test_noqa_suppresses_the_finding():
    """A local import is sometimes the only way to break a cycle; noqa says so."""
    src = "def f():\n    from x import y  # noqa: PLC0415\n    return y\n"
    assert analyze("m.py", src) == []


def test_unparseable_file_is_skipped():
    assert analyze("m.py", "def f(:\n") == []


def test_non_python_file_is_skipped():
    assert analyze("notes.md", "def f():\n    import json\n") == []


# --- diff scoping -----------------------------------------------------------


def test_scope_keeps_finding_on_a_changed_line():
    assert len(analyze("m.py", "def f():\n    import json\n", scope={2})) == 1


def test_scope_drops_finding_outside_the_diff():
    """A pre-existing local import elsewhere in a touched file must not block."""
    assert analyze("m.py", "def f():\n    import json\n", scope={1}) == []


def test_empty_scope_drops_everything():
    assert analyze("m.py", "def f():\n    import json\n", scope=set()) == []


# --- rendering and scan_paths -----------------------------------------------


def test_render_names_the_import_and_the_escape_hatch():
    finding = analyze("m.py", "def f():\n    import json\n")[0]
    rendered = finding.render()
    assert "m.py:2" in rendered
    assert "import json" in rendered
    assert "noqa" in rendered, "the author needs to be told the escape hatch"


def test_scan_paths_reads_files(tmp_path: Path):
    target = tmp_path / "m.py"
    target.write_text("def f():\n    import json\n    return json\n")
    findings = scan_paths([str(target)], diff=False)
    assert len(findings) == 1


def test_scan_paths_skips_unreadable(tmp_path: Path):
    assert scan_paths([str(tmp_path / "missing.py")], diff=False) == []


# --- agreement with ruff's own rule -----------------------------------------


@pytest.mark.parametrize(
    "src,expected",
    [
        ("def f():\n    import json\n", 1),
        ("import json\n", 0),
        ("class C:\n    import json\n", 1),
    ],
)
def test_matches_ruff_plc0415_semantics(src, expected):
    """This check exists to be PLC0415, scoped to the diff rather than the file."""
    assert len(analyze("m.py", src)) == expected


# --- guard wiring -----------------------------------------------------------


def _load_guard(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, TEMPLATES / relpath)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "relpath,name",
    [
        ("git_commit_guard.py", "_claude_commit_guard_il"),
        ("multi/commit_guard.py", "_multi_commit_guard_il"),
    ],
)
def test_commit_guards_run_the_import_check(relpath, name):
    mod = _load_guard(relpath, name)
    assert mod.IMPORT_LINT_CMD == "klaussy import-lint --diff __KLAUSSY_PATHS__"
    resolved = mod._resolve(mod.IMPORT_LINT_CMD, ["a.py", "b.py"])
    assert resolved == "klaussy import-lint --diff a.py b.py"
