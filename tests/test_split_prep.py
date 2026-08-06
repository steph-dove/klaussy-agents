"""Tests for the split-prep layer proposer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from klaussy.split_prep import FileNode as FN
from klaussy.split_prep import (
    _added_line_numbers,
    _docstring_lines,
    _file_at,
    _python_imports,
    _resolve_jsts,
    _resolve_python,
    build_layers,
    prepare_split,
    render_dict,
    render_markdown,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _node(path: str, added: int = 10, comment_added: int = 0, graphed: bool = True) -> FN:
    return FN(
        path=path,
        added=added,
        removed=0,
        comment_added=comment_added,
        language="python",
        graphed=graphed,
    )


class TestAddedLineNumbers:
    def test_tracks_the_new_side_across_hunks(self):
        body = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -1,2 +1,3 @@\n"
            " keep\n"
            "+added_at_2\n"
            " keep\n"
            "@@ -10,1 +11,2 @@\n"
            "-gone\n"
            "+added_at_11\n"
        )
        assert _added_line_numbers(body) == {2, 11}

    def test_removals_do_not_advance_the_new_side(self):
        body = "@@ -1,3 +1,1 @@\n-a\n-b\n+c\n"
        assert _added_line_numbers(body) == {1}

    def test_no_newline_marker_is_ignored(self):
        body = "@@ -1,1 +1,1 @@\n+a\n\\ No newline at end of file\n"
        assert _added_line_numbers(body) == {1}

    def test_an_added_increment_line_is_not_mistaken_for_a_header(self):
        body = "@@ -1,0 +1,3 @@\n+++i;\n+b\n+c\n"
        assert _added_line_numbers(body) == {1, 2, 3}

    def test_headers_before_the_first_hunk_are_still_skipped(self):
        body = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,0 +1,1 @@\n+only\n"
        assert _added_line_numbers(body) == {1}


class TestDocstringLines:
    def test_spans_a_multiline_docstring(self):
        source = '"""One\ntwo\nthree"""\nx = 1\n'
        assert _docstring_lines(source) == {1, 2, 3}

    def test_finds_nested_function_docstrings(self):
        source = 'def f():\n    """Doc."""\n    return 1\n'
        assert _docstring_lines(source) == {2}

    def test_a_bare_string_expression_is_not_a_docstring(self):
        # Only the *first* statement of a module/class/def counts.
        source = "x = 1\n'not a docstring'\n"
        assert _docstring_lines(source) == set()

    def test_unparseable_source_yields_nothing(self):
        assert _docstring_lines("def (:\n") == set()


class TestPythonResolution:
    def test_matches_the_longest_dotted_prefix(self):
        index = {"app.schema": "app/schema.py", "app": "app/__init__.py"}
        paths = set(index.values())
        got = _resolve_python("app/api.py", "app.schema", 0, index, paths)
        assert got == "app/schema.py"

    def test_src_layout_module_names_resolve(self):
        # `src/pkg/mod.py` is imported as `pkg.mod`, not `src.pkg.mod`.
        index = {"pkg.mod": "src/pkg/mod.py", "src.pkg.mod": "src/pkg/mod.py"}
        got = _resolve_python("src/pkg/other.py", "pkg.mod", 0, index, {"src/pkg/mod.py"})
        assert got == "src/pkg/mod.py"

    def test_relative_import_resolves_against_the_importer(self):
        paths = {"app/schema.py", "app/api.py"}
        got = _resolve_python("app/api.py", "schema", 1, {}, paths)
        assert got == "app/schema.py"

    def test_unknown_module_is_not_an_edge(self):
        assert _resolve_python("app/api.py", "requests", 0, {}, {"app/api.py"}) is None


class TestUnparseablePython:
    def test_parse_failure_is_none_not_an_empty_import_list(self):
        # [] means "imports nothing" and belongs in layer 1; None means "couldn't
        # read it" and belongs nowhere until a human places it. Collapsing the two
        # drops an unparseable file into the bottom layer on a guess.
        assert _python_imports("def (:\n") is None
        assert _python_imports("x = 1\n") == []

    def test_unparseable_file_is_reported_as_ungraphed(self, tmp_path: Path):
        repo = tmp_path / "broken"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "t@t.t")
        _git(repo, "config", "user.name", "t")
        _write(repo, "README.md", "# base\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "base")
        base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()

        _write(repo, "app/ok.py", "VALUE = 1\n")
        # Valid to git, unparseable to ast — e.g. a template or newer syntax.
        _write(repo, "app/broken.py", "def oops(:\n    pass\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "wip")

        payload = prepare_split(repo=repo, base_branch=base)
        assert "app/broken.py" in payload.ungraphed
        assert all("app/broken.py" not in lyr.paths for lyr in payload.layers)
        assert any("app/ok.py" in lyr.paths for lyr in payload.layers)


class TestFileAt:
    def test_absent_path_is_none_not_an_error(self, tmp_path: Path):
        repo = tmp_path / "r"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.email", "t@t.t")
        _git(repo, "config", "user.name", "t")
        _write(repo, "a.py", "x = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "c")
        assert _file_at(repo, "HEAD", "never-existed.py") is None
        assert _file_at(repo, "HEAD", "a.py") == "x = 1\n"

    def test_a_real_git_failure_raises_rather_than_zeroing_the_count(self, tmp_path: Path):
        repo = tmp_path / "r2"
        repo.mkdir()
        _git(repo, "init")
        with pytest.raises(RuntimeError, match="git show"):
            _file_at(repo, "no-such-ref", "a.py")


class TestJstsResolution:
    def test_relative_specifier_gains_an_extension(self):
        paths = {"web/client.ts", "web/Form.tsx"}
        assert _resolve_jsts("web/Form.tsx", "./client", paths) == "web/client.ts"

    def test_directory_specifier_resolves_to_index(self):
        paths = {"web/api/index.ts"}
        assert _resolve_jsts("web/Form.tsx", "./api", paths) == "web/api/index.ts"

    def test_parent_traversal(self):
        paths = {"web/lib/http.ts"}
        assert _resolve_jsts("web/ui/Form.tsx", "../lib/http", paths) == "web/lib/http.ts"

    def test_alias_specifier_tries_conventional_roots(self):
        paths = {"src/lib/http.ts"}
        assert _resolve_jsts("web/Form.tsx", "@/lib/http", paths) == "src/lib/http.ts"

    def test_bare_specifier_is_a_package_not_a_layer(self):
        assert _resolve_jsts("web/Form.tsx", "react", {"web/react.ts"}) is None


class TestBuildLayers:
    def test_orders_dependencies_below_their_dependents(self):
        files = [_node("api.py"), _node("service.py"), _node("schema.py")]
        edges = [("api.py", "service.py"), ("service.py", "schema.py")]
        layers = build_layers(files, edges)
        assert [lyr.paths for lyr in layers] == [["schema.py"], ["service.py"], ["api.py"]]

    def test_independent_files_share_the_bottom_layer(self):
        files = [_node("a.py"), _node("b.py")]
        assert [lyr.paths for lyr in build_layers(files, [])] == [["a.py", "b.py"]]

    def test_a_cycle_lands_in_one_layer_and_is_named(self):
        files = [_node("left.py"), _node("right.py"), _node("top.py")]
        edges = [("left.py", "right.py"), ("right.py", "left.py"), ("top.py", "left.py")]
        layers = build_layers(files, edges)
        assert [lyr.paths for lyr in layers] == [["left.py", "right.py"], ["top.py"]]
        assert layers[0].cycles == [["left.py", "right.py"]]
        # A layer whose members merely share a depth carries no cycle claim.
        assert layers[1].cycles == []

    def test_diamond_puts_the_join_above_both_sides(self):
        files = [_node(n) for n in ("base.py", "l.py", "r.py", "top.py")]
        edges = [
            ("l.py", "base.py"),
            ("r.py", "base.py"),
            ("top.py", "l.py"),
            ("top.py", "r.py"),
        ]
        layers = build_layers(files, edges)
        assert [lyr.paths for lyr in layers] == [["base.py"], ["l.py", "r.py"], ["top.py"]]

    def test_ungraphed_files_are_left_out_of_the_layers(self):
        files = [_node("a.py"), _node("schema.sql", graphed=False)]
        assert [lyr.paths for lyr in build_layers(files, [])] == [["a.py"]]

    def test_code_lines_exclude_comments(self):
        files = [_node("a.py", added=30, comment_added=12)]
        assert build_layers(files, [])[0].code_lines == 18


@pytest.fixture
def layered_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo whose branch adds schema <- service <- api, a TS pair, and a .sql."""
    repo = tmp_path / "layered"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _write(repo, "README.md", "# base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()

    _write(
        repo,
        "app/schema.py",
        '"""Invites.\n\nTwo lines of docstring.\n"""\n\n# A comment about statuses.\n'
        "STATUSES = ('pending',)\n",
    )
    _write(
        repo,
        "app/service.py",
        "from app.schema import STATUSES\n\n\ndef create():\n    return STATUSES\n",
    )
    _write(
        repo,
        "app/api.py",
        "from app.service import create\n\n\ndef post():\n    return create()\n",
    )
    _write(repo, "web/client.ts", "export const get = () => fetch('/x');\n")
    _write(repo, "web/Form.tsx", "import { get } from './client';\nexport const F = () => get();\n")
    _write(repo, "db/init.sql", "CREATE TABLE invites (id INT);\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat: invites")
    return repo, base


class TestPrepareSplitEndToEnd:
    def test_proposes_layers_in_dependency_order(self, layered_repo):
        repo, base = layered_repo
        payload = prepare_split(repo=repo, base_branch=base)
        layers = [lyr.paths for lyr in payload.layers]
        # schema and client.ts depend on nothing in the change; api sits on top.
        assert "app/schema.py" in layers[0]
        assert "web/client.ts" in layers[0]
        assert layers[1] == ["app/service.py", "web/Form.tsx"]
        assert layers[2] == ["app/api.py"]

    def test_sql_is_reported_as_ungraphed_not_guessed_at(self, layered_repo):
        repo, base = layered_repo
        payload = prepare_split(repo=repo, base_branch=base)
        assert payload.ungraphed == ["db/init.sql"]
        assert all("db/init.sql" not in lyr.paths for lyr in payload.layers)

    def test_counts_comments_and_docstrings_as_non_code(self, layered_repo):
        repo, base = layered_repo
        payload = prepare_split(repo=repo, base_branch=base)
        schema = next(f for f in payload.files if f.path == "app/schema.py")
        # 4 docstring lines + 1 `#` comment, all newly added.
        assert schema.comment_added == 5
        assert schema.code_lines == schema.lines - 5
        assert payload.code_lines == payload.total_lines - payload.comment_lines

    def test_edges_point_from_importer_to_imported(self, layered_repo):
        repo, base = layered_repo
        payload = prepare_split(repo=repo, base_branch=base)
        assert ("app/api.py", "app/service.py") in payload.edges
        assert ("web/Form.tsx", "web/client.ts") in payload.edges

    def test_markdown_names_the_figure_to_decide_on(self, layered_repo):
        repo, base = layered_repo
        out = render_markdown(prepare_split(repo=repo, base_branch=base))
        assert "Code lines:" in out
        assert "Proposed layers" in out
        assert "static imports only" in out, "the caveat has to ship with the proposal"

    def test_json_is_serializable_and_complete(self, layered_repo):
        import json

        repo, base = layered_repo
        data = render_dict(prepare_split(repo=repo, base_branch=base))
        json.dumps(data)
        assert data["layers"] and data["files"] and data["edges"]
        assert data["code_lines"] == data["total_lines"] - data["comment_lines"]

    def test_empty_diff_yields_no_layers(self, layered_repo):
        repo, _ = layered_repo
        payload = prepare_split(repo=repo, base_branch="HEAD")
        assert payload.files == []
        assert payload.layers == []
        # Rendering an empty payload must not divide by zero.
        assert "Proposed layers" in render_markdown(payload)
