"""Deterministic function-local import detector — a block-only precommit check.

Same ground as ruff's PLC0415, but scoped to the lines in flight so an unrelated
local import elsewhere in a touched file doesn't block the commit. Block-only: a
local import is occasionally the only way to break a cycle or defer an optional
dependency, so a `# noqa` on the line marks it deliberate and is honored.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from klaussy.comment_lint import changed_lines

_PY_EXT = {".py", ".pyi"}

# Nodes that open a new scope. An import nested in a module-level `if
# TYPE_CHECKING:` or `try:` block is still top-level and never flagged.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class Finding:
    """One function-local import the guard should block on."""

    path: str
    line: int  # 1-based
    statement: str  # the import as written, e.g. "import json"
    scope: str  # enclosing function/class name

    def render(self) -> str:
        return (
            f"{self.path}:{self.line}: `{self.statement}` sits inside `{self.scope}` — "
            "move it to the top of the file, or mark the line `# noqa` if it breaks "
            "an import cycle or defers an optional dependency"
        )


def _statement(node: ast.Import | ast.ImportFrom) -> str:
    """The import rendered back to source, near enough to recognise on sight."""
    if isinstance(node, ast.Import):
        return "import " + ", ".join(a.name for a in node.names)
    module = "." * node.level + (node.module or "")
    return f"from {module} import " + ", ".join(a.name for a in node.names)


def _collect(node: ast.AST, scope: str | None, out: list[tuple[ast.stmt, str]]) -> None:
    """Walk `node`, recording imports that sit inside a function or class."""
    for child in ast.iter_child_nodes(node):
        inner = child.name if isinstance(child, _SCOPES) else scope
        if scope and isinstance(child, (ast.Import, ast.ImportFrom)):
            out.append((child, scope))
        _collect(child, inner, out)


def _is_suppressed(text_lines: list[str], lineno: int) -> bool:
    """True if the import's own line carries a `# noqa`, as ruff would read it."""
    if not 1 <= lineno <= len(text_lines):
        return False
    return "# noqa" in text_lines[lineno - 1]


def analyze(path: str, text: str, scope: set[int] | None = None) -> list[Finding]:
    """Return function-local import findings for one file. Empty when clean.

    When `scope` is a set of line numbers, only findings on those lines are
    returned — used to limit the check to the diff in flight so a pre-existing
    local import elsewhere in the file doesn't block a commit. `None` (the
    default) reports across the whole file.
    """
    if Path(path).suffix.lower() not in _PY_EXT:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []  # unparseable — ruff will have its own say
    lines = text.splitlines()
    found: list[tuple[ast.stmt, str]] = []
    _collect(tree, None, found)

    findings = [
        Finding(path, node.lineno, _statement(node), enclosing)  # type: ignore[arg-type]
        for node, enclosing in found
        if not _is_suppressed(lines, node.lineno)
    ]
    if scope is not None:
        findings = [f for f in findings if f.line in scope]
    return sorted(findings, key=lambda f: f.line)


def scan_paths(paths: list[str], *, diff: bool) -> list[Finding]:
    """Scan each path; with `diff`, restrict to lines changed vs HEAD."""
    findings: list[Finding] = []
    for path in paths:
        try:
            text = Path(path).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        scope = changed_lines(path) if diff else None
        findings.extend(analyze(path, text, scope))
    return findings
