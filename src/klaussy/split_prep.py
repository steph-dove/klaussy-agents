"""Deterministic layer proposal for the split-pr skill: where a large change can
be cut, from the import graph rather than from filenames.

Edges come from the code — Python through `ast`, JS/TS through import/require
extraction — and layers come off a topological sort of the edges that stay inside
the change. Anything else is reported as ungraphed rather than placed on a guess:
a wrong edge proposes an order that can't build, which is worse than a missing
one. Comment sizing reuses `comment_lint`'s extractors plus docstring spans from
`ast`, counted on the added side only.
"""

from __future__ import annotations

import ast
import posixpath
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from klaussy.comment_lint import comment_records
from klaussy.review_prep import _detect_base, _run_git, classify, split_file_diffs

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

PYTHON_SUFFIXES = (".py", ".pyi")
JSTS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Tried in order when a JS/TS specifier omits its extension, matching how
# bundlers resolve `./foo` to `./foo.ts` or `./foo/index.ts`.
_JSTS_RESOLUTION_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".d.ts")

# `@/x` and `~/x` are the near-universal "from the project root" aliases (Next,
# Vite, tsconfig paths). Resolved against a few conventional roots rather than by
# reading tsconfig, which would mean parsing JSON with comments.
_JSTS_ALIAS_PREFIXES = ("@/", "~/")
_JSTS_ALIAS_ROOTS = ("", "src/", "app/", "lib/")

_JSTS_IMPORT_PATTERNS = (
    # import x from 'y' / export { a } from 'y' / import 'y'
    re.compile(r"""(?:^|\s)(?:import|export)\b[^;'"]*?from\s*['"]([^'"]+)['"]"""),
    re.compile(r"""(?:^|\s)import\s*['"]([^'"]+)['"]"""),
    # require('y') and dynamic import('y')
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
)


@dataclass(frozen=True)
class FileNode:
    """One changed file: its size, its comment estimate, and how it was graphed."""

    path: str
    added: int
    removed: int
    comment_added: int
    language: str
    graphed: bool

    @property
    def lines(self) -> int:
        return self.added + self.removed

    @property
    def code_lines(self) -> int:
        """Changed lines that aren't comment — the figure the split decision uses."""
        return self.lines - self.comment_added


@dataclass(frozen=True)
class Layer:
    """One proposed layer of the stack, bottom-first."""

    index: int
    paths: list[str]
    lines: int
    code_lines: int
    # Import cycles inside this layer; each group must move together, since no cut
    # exists between files that refer to each other. Files not in a group share
    # only a depth and can still be moved out by hand.
    cycles: list[list[str]]


@dataclass(frozen=True)
class SplitPayload:
    """Proposed layers plus everything needed to argue with the proposal."""

    files: list[FileNode]
    edges: list[tuple[str, str]]
    layers: list[Layer]
    ungraphed: list[str]
    base: str

    @property
    def total_lines(self) -> int:
        return sum(f.lines for f in self.files)

    @property
    def comment_lines(self) -> int:
        return sum(f.comment_added for f in self.files)

    @property
    def code_lines(self) -> int:
        return self.total_lines - self.comment_lines

    @property
    def comment_heavy(self) -> list[FileNode]:
        """Files where comment is a third or more of what was added, worst first.

        The 15-line floor keeps a tiny file with one comment on two lines of code
        off a list meant to point at bloat.
        """
        heavy = [f for f in self.files if f.added >= 15 and f.comment_added * 3 >= f.added]
        return sorted(heavy, key=lambda f: f.comment_added, reverse=True)


def _language(path: str) -> str:
    if path.endswith(PYTHON_SUFFIXES):
        return "python"
    if path.endswith(JSTS_SUFFIXES):
        return "js/ts"
    return "other"


def _file_at(repo: Path, ref: str, path: str) -> str | None:
    """File content at `ref`, or None when it isn't there (deleted, or unborn ref)."""
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    return out.stdout if out.returncode == 0 else None


# --- comment measurement ----------------------------------------------------


def _added_line_numbers(body: str) -> set[int]:
    """New-side line numbers of the `+` lines in one file's diff section.

    Walks each hunk counting the post-image, so the numbers line up with the
    file as it exists at the ref — which is what the comment extractors read.
    """
    out: set[int] = set()
    line_no = 0
    for line in body.splitlines():
        if (m := _HUNK.match(line)) is not None:
            line_no = int(m.group(1))
            continue
        if line_no == 0 or line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            out.add(line_no)
            line_no += 1
        elif line.startswith("-"):
            continue  # old side only; doesn't advance the new-side counter
        elif line.startswith("\\"):
            continue  # "\ No newline at end of file"
        else:
            line_no += 1
    return out


def _docstring_lines(source: str) -> set[int]:
    """Every line a module/class/function docstring occupies.

    `comment_lint` reads `#` comments via tokenize and deliberately exempts
    docstrings, since a docstring isn't the narration it hunts. For sizing a diff
    they count: five lines of docstring inflate a PR exactly as much as five
    lines of comment, and the cleanup pass trims them under the same rule.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    out: set[int] = set()
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            out.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return out


def _comment_lines_at(repo: Path, ref: str, path: str) -> set[int]:
    """Line numbers that are comment (or docstring) in `path` as of `ref`."""
    source = _file_at(repo, ref, path)
    if source is None:
        return set()
    lines = {row for row, full, _ in comment_records(path, source) if full}
    if path.endswith(".py"):
        lines |= _docstring_lines(source)
    return lines


# --- import graph -----------------------------------------------------------


def _python_module_index(paths: set[str]) -> dict[str, str]:
    """Map every plausible dotted module name of each changed .py file to its path.

    A src-layout file `src/pkg/mod.py` is importable as `pkg.mod`, so each
    trailing path suffix is registered. The longest match wins at lookup time.
    """
    index: dict[str, str] = {}
    for path in sorted(paths):
        if not path.endswith(".py"):
            continue
        parts = path[: -len(".py")].split("/")
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):
            index.setdefault(".".join(parts[i:]), path)
    return index


def _python_imports(source: str) -> list[tuple[str, int]] | None:
    """(module, relative-level) for every import in a Python file.

    `None` means the file could not be parsed, which is not the same as an empty
    list: a file with no imports belongs at the bottom of the stack, and one we
    couldn't read belongs nowhere until a human places it. Collapsing the two
    would silently drop an unparseable file into layer 1.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            found.append((base, node.level))
            # `from pkg import mod` — mod may itself be a module in the change.
            found.extend((f"{base}.{a.name}" if base else a.name, node.level) for a in node.names)
    return found


def _resolve_python(
    importer: str, module: str, level: int, index: dict[str, str], paths: set[str]
) -> str | None:
    if level == 0:
        # Longest dotted prefix that names a changed module.
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            hit = index.get(".".join(parts[:i]))
            if hit:
                return hit
        return None
    # Relative: walk up `level - 1` packages from the importer's directory.
    base = posixpath.dirname(importer)
    for _ in range(level - 1):
        base = posixpath.dirname(base)
    target = posixpath.join(base, module.replace(".", "/")) if module else base
    for candidate in (f"{target}.py", f"{target}/__init__.py"):
        if candidate in paths:
            return candidate
    return None


def _jsts_imports(source: str) -> list[str]:
    specs: list[str] = []
    for pattern in _JSTS_IMPORT_PATTERNS:
        specs.extend(m.group(1) for m in pattern.finditer(source))
    return specs


def _resolve_jsts(importer: str, spec: str, paths: set[str]) -> str | None:
    if spec.startswith("."):
        target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
        return _first_existing(target, paths)
    for prefix in _JSTS_ALIAS_PREFIXES:
        if spec.startswith(prefix):
            rest = spec[len(prefix) :]
            for root in _JSTS_ALIAS_ROOTS:
                hit = _first_existing(posixpath.normpath(root + rest), paths)
                if hit:
                    return hit
            return None
    # A bare specifier is a package, not a layer of this change.
    return None


def _first_existing(target: str, paths: set[str]) -> str | None:
    if target in paths:
        return target
    for suffix in _JSTS_RESOLUTION_SUFFIXES:
        if (candidate := target + suffix) in paths:
            return candidate
    for suffix in _JSTS_RESOLUTION_SUFFIXES:
        if (candidate := f"{target}/index{suffix}") in paths:
            return candidate
    return None


def build_edges(repo: Path, ref: str, paths: set[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (edges, ungraphed). An edge (a, b) means "a imports b"."""
    index = _python_module_index(paths)
    edges: set[tuple[str, str]] = set()
    ungraphed: list[str] = []
    for path in sorted(paths):
        language = _language(path)
        if language == "other":
            ungraphed.append(path)
            continue
        source = _file_at(repo, ref, path)
        if source is None:
            ungraphed.append(path)
            continue
        if language == "python":
            imports = _python_imports(source)
            if imports is None:
                # Unparseable: report it rather than treat "no imports found" as
                # "depends on nothing", which would bury it in the bottom layer.
                ungraphed.append(path)
                continue
            for module, level in imports:
                target = _resolve_python(path, module, level, index, paths)
                if target and target != path:
                    edges.add((path, target))
        else:
            for spec in _jsts_imports(source):
                target = _resolve_jsts(path, spec, paths)
                if target and target != path:
                    edges.add((path, target))
    return sorted(edges), ungraphed


# --- layering ---------------------------------------------------------------


def _reachable(nodes: list[str], deps: dict[str, set[str]]) -> dict[str, set[str]]:
    """Transitive closure by BFS from each node. Fine at changed-file scale."""
    closure: dict[str, set[str]] = {}
    for start in nodes:
        seen: set[str] = set()
        queue = list(deps.get(start, ()))
        while queue:
            node = queue.pop()
            if node in seen:
                continue
            seen.add(node)
            queue.extend(deps.get(node, ()))
        closure[start] = seen
    return closure


def _components(nodes: list[str], deps: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components: mutually-importing files must share a layer.

    Two nodes are in the same component when each reaches the other. Quadratic,
    and deliberately so — the graph is one change's files, and an obviously
    correct closure beats a clever traversal nobody can check.
    """
    closure = _reachable(nodes, deps)
    seen: set[str] = set()
    out: list[list[str]] = []
    for node in nodes:
        if node in seen:
            continue
        group = [node] + [
            other
            for other in nodes
            if other != node and other in closure[node] and node in closure[other]
        ]
        seen.update(group)
        out.append(sorted(group))
    return out


def build_layers(files: list[FileNode], edges: list[tuple[str, str]]) -> list[Layer]:
    """Topological levels over the changed files, bottom (depended-upon) first."""
    graphed = [f.path for f in files if f.graphed]
    if not graphed:
        return []
    allowed = set(graphed)
    deps: dict[str, set[str]] = {p: set() for p in graphed}
    for src, dst in edges:
        if src in allowed and dst in allowed:
            deps[src].add(dst)

    components = _components(graphed, deps)
    owner = {path: i for i, comp in enumerate(components) for path in comp}
    # Condense to a DAG over components, dropping the self-edges cycles create.
    condensed: dict[int, set[int]] = {i: set() for i in range(len(components))}
    for src, targets in deps.items():
        for dst in targets:
            if owner[src] != owner[dst]:
                condensed[owner[src]].add(owner[dst])

    level: dict[int, int] = {}

    def depth(component: int, stack: frozenset[int] = frozenset()) -> int:
        if component in level:
            return level[component]
        # `stack` is belt-and-braces: the condensation is acyclic by construction.
        children = [c for c in condensed[component] if c not in stack]
        value = 1 + max((depth(c, stack | {component}) for c in children), default=-1)
        level[component] = value
        return value

    for component in range(len(components)):
        depth(component)

    by_size = {f.path: f for f in files}
    layers: list[Layer] = []
    for index, depth_value in enumerate(sorted({v for v in level.values()})):
        paths = sorted(
            path
            for component, value in level.items()
            if value == depth_value
            for path in components[component]
        )
        cycles = [
            components[component]
            for component, value in level.items()
            if value == depth_value and len(components[component]) > 1
        ]
        layers.append(
            Layer(
                index=index + 1,
                paths=paths,
                lines=sum(by_size[p].lines for p in paths),
                code_lines=sum(by_size[p].code_lines for p in paths),
                cycles=sorted(cycles),
            )
        )
    return layers


# --- entry point ------------------------------------------------------------


def prepare_split(
    repo: Path | str = ".", base_branch: str | None = None, ref: str = "HEAD"
) -> SplitPayload:
    """Analyse the branch diff and propose stack layers from the import graph."""
    repo = Path(repo).resolve()
    base = base_branch or _detect_base(repo)
    diff_text = _run_git(["diff", f"{base}...{ref}"], repo)

    files: list[FileNode] = []
    for fd in split_file_diffs(diff_text):
        keep, _ = classify(fd)
        if not keep:
            continue
        comment_lines = _comment_lines_at(repo, ref, fd.path)
        added_lines = _added_line_numbers(fd.body)
        language = _language(fd.path)
        files.append(
            FileNode(
                path=fd.path,
                added=fd.added,
                removed=fd.removed,
                comment_added=len(comment_lines & added_lines),
                language=language,
                graphed=language != "other",
            )
        )

    paths = {f.path for f in files}
    edges, ungraphed = build_edges(repo, ref, paths)
    ungraphed_set = set(ungraphed)
    files = [replace(f, graphed=f.graphed and f.path not in ungraphed_set) for f in files]
    layers = build_layers(files, edges)
    return SplitPayload(
        files=files, edges=edges, layers=layers, ungraphed=sorted(ungraphed), base=base
    )


def render_markdown(payload: SplitPayload) -> str:
    """Render the proposal for the split-pr skill to read."""
    lines: list[str] = []
    comment_pct = round(100 * payload.comment_lines / payload.total_lines) if payload.files else 0
    lines.append(
        f"<!-- split-prep: {len(payload.files)} file(s), {payload.total_lines} changed "
        f"line(s), {payload.code_lines} after comments ({comment_pct}% comment) -->"
    )
    lines.append("")
    lines.append("## Size")
    lines.append("")
    lines.append(f"- Reviewable changed lines: **{payload.total_lines}**")
    lines.append(f"- Added comment/docstring lines: **{payload.comment_lines}**")
    lines.append(f"- **Code lines: {payload.code_lines}** — decide the split on this figure")
    if payload.comment_heavy:
        lines.append("")
        lines.append("Comment-heavy files, worst first — start the cleanup pass here:")
        lines.append("")
        for f in payload.comment_heavy:
            lines.append(f"- `{f.path}` — {f.comment_added} of {f.added} added lines are comment")

    lines.append("")
    lines.append("## Proposed layers (from the import graph)")
    lines.append("")
    if payload.layers:
        lines.append("Bottom first. Layer N may import layer N-1, never the reverse.")
        lines.append("")
        for layer in payload.layers:
            lines.append(f"**Layer {layer.index}** — {layer.code_lines} code line(s)")
            for path in layer.paths:
                lines.append(f"  - `{path}`")
            for cycle in layer.cycles:
                names = ", ".join(f"`{p}`" for p in cycle)
                lines.append(f"  - ⟲ {names} import each other — they cannot be separated")
            lines.append("")
    else:
        lines.append("_No graphable files — fall back to the heuristic ladder._")
        lines.append("")

    if payload.ungraphed:
        lines.append(f"## Ungraphed ({len(payload.ungraphed)} file(s))")
        lines.append("")
        lines.append(
            "No import graph for these — place them by hand using the dependency "
            "ladder, and check them first if a layer fails to build:"
        )
        lines.append("")
        for path in payload.ungraphed:
            lines.append(f"- `{path}`")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- Layers come from **static imports only**. Runtime wiring — DI containers, "
        "registries, dynamic imports, template/string references, URL routing tables, "
        "and database migrations ordered by filename — produces no edge here. Read the "
        "proposal, don't just accept it."
    )
    lines.append(
        "- Comment counts cover **added** lines only, via the same extractors the "
        "comment guard uses (Python through `tokenize`, so a `#` inside a string isn't "
        "counted; docstrings included). Comment lines a change *deletes* are not "
        "discounted — reading the pre-image would be needed, and deletions rarely "
        "inflate a diff."
    )
    lines.append(
        "- A missing edge merges two layers that could have been split; a wrong edge "
        "proposes an order that won't build. Phase 5's per-layer build is what settles it."
    )
    return "\n".join(lines) + "\n"


def render_dict(payload: SplitPayload) -> dict:
    """Structured form of the proposal (for `--json`)."""
    return {
        "base": payload.base,
        "total_lines": payload.total_lines,
        "comment_lines": payload.comment_lines,
        "code_lines": payload.code_lines,
        "files": [
            {
                "path": f.path,
                "added": f.added,
                "removed": f.removed,
                "comment_added": f.comment_added,
                "code_lines": f.code_lines,
                "language": f.language,
                "graphed": f.graphed,
            }
            for f in payload.files
        ],
        "edges": [{"from": a, "to": b} for a, b in payload.edges],
        "layers": [
            {
                "index": lyr.index,
                "paths": lyr.paths,
                "lines": lyr.lines,
                "code_lines": lyr.code_lines,
                "cycles": lyr.cycles,
            }
            for lyr in payload.layers
        ],
        "ungraphed": payload.ungraphed,
    }
