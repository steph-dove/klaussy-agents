# Copyright 2026 Dovatech LLC. SPDX-License-Identifier: FSL-1.1-MIT
"""Deterministic pre-processor for the review skill: trim a branch diff to what's
actually worth reviewing before it reaches the model.

A review's wall-clock is dominated by how many tokens the model has to read, and
much of a large diff is noise no LLM should spend prefill or attention on:
lockfiles, generated/vendored code, minified assets, binaries, pure renames.
`prepare_review` runs the same `git diff` the skill would, drops those files
deterministically, and returns both the trimmed reviewable diff and an explicit
manifest of what was excluded and why — so nothing is silently hidden from the
reviewer (silent truncation reads as "covered everything" when it didn't).

This is the cheap, language-agnostic half of "make review faster": fewer tokens
in. The expensive half (prompt-caching the diff across parallel sub-agents) lives
in the skill/orchestration layer, not here.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from klaussy import base_branch

# Dependency-manifest locks: huge, machine-generated, never hand-reviewed line by
# line. The *manifest* change (package.json, pyproject.toml) stays reviewable;
# only the lockfile is dropped.
LOCKFILES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "pdm.lock",
        "Cargo.lock",
        "go.sum",
        "Gemfile.lock",
        "composer.lock",
        "flake.lock",
    }
)

# Any path component here marks a vendored / build-output / generated tree.
NOISE_DIR_PARTS = frozenset(
    {
        "node_modules",
        "vendor",
        "dist",
        "build",
        "out",
        ".next",
        "__generated__",
        "generated",
        ".egg-info",
    }
)

# Minified or sourcemap artifacts, plus common codegen suffixes.
NOISE_SUFFIXES = (".min.js", ".min.css", ".map")
GENERATED_SUFFIXES = (".pb.go", "_pb2.py", "_pb2_grpc.py", ".g.dart", ".freezed.dart")

# At or above this many reviewable lines the review fans out to lens sub-agents.
PARALLEL_THRESHOLD = 150

# Correctness runs twice: one look finds a given bug only about half the time.
BASE_LENSES = ("correctness", "correctness-2", "architecture", "security", "scope")

# A diff bigger than this is split into chunks: an agent sees only the start of a tool
# output much past ~30k characters, so one oversized read leaves most of a big PR unseen.
CHUNK_CHARS = 24_000
# An added line this long can't be split into chunks and no reviewer reads it, so it's
# elided; a file whose added lines are all this long is minified, whatever its suffix says.
MINIFIED_LINE_CHARS = 5_000
# Past this many chunks the lowest-priority files (docs, then tests) aren't reviewed, and
# the manifest says so.
MAX_CHUNKS = 10

_TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs)/|(^|/)test_[^/]+$|_test\.\w+$|\.(test|spec)\.\w+$"
)
_DOC_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")
_CODE_SUFFIXES = (
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".kts",
    ".rb", ".php", ".cs", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".m", ".mm", ".scala",
    ".dart", ".lua", ".ex", ".exs", ".erl", ".clj", ".hs", ".ml", ".fs", ".zig", ".sql",
    ".sh", ".bash", ".zsh", ".ps1", ".vue", ".svelte", ".css", ".scss", ".sass", ".less",
    ".html", ".r", ".jl", ".pl", ".groovy", ".tf", ".proto",
)

_AGENTIC_PATH = re.compile(
    r"(^|/)(skills|agents|\.claude|evals)/"
    r"|(^|/)mcp_[^/]*\.(py|ts|js)$|(^|/)mcp-server[^/]*$|(^|/)\.mcp\.json$"
    r"|(^|/)eval_[^/]*\.(py|ts|js)$|\.eval\.(py|ts|js)$"
    r"|(^|/)SKILL\.md$|\.prompt\.md$"
)
_AGENTIC_CODE = re.compile(
    r"^\+.*(\b(import|from|require\()\s*['\"]?(anthropic|openai|langchain|langgraph|llama_index"
    r"|mcp|inspect_ai|langsmith|promptfoo|ragas)\b|@anthropic-ai/sdk|@openai/openai"
    r"|\bsystem_prompt\s*=)",
    re.MULTILINE,
)
_DESIGN_DOC_PATH = re.compile(
    r"(^|/)(docs?/adrs?|adr|docs/decisions|docs/architecture/decisions|rfcs|docs/rfcs"
    r"|docs/design|design-docs)/"
    r"|(^|/)(\d{4}-[^/]+|ADR-\d+-[^/]+|[^/]+\.(adr|rfc|design))\.md$"
)
_DESIGN_DOC_HEADINGS = (
    ("## Status", "## Context", "## Decision", "## Consequences"),
    ("## Context and Problem Statement", "## Considered Options", "## Decision Outcome"),
    ("## Motivation", "## Rationale and alternatives", "## Drawbacks"),
)

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_BINARY = re.compile(r"^(Binary files .* differ|GIT binary patch)$", re.MULTILINE)


@dataclass(frozen=True)
class FileDiff:
    """One file's section of a unified diff, with cheap pre-computed stats."""

    path: str
    body: str
    added: int
    removed: int
    binary: bool
    has_hunks: bool


@dataclass(frozen=True)
class Decision:
    """Keep/drop verdict for one file, with the reason and its line counts."""

    path: str
    kept: bool
    reason: str
    added: int
    removed: int


@dataclass(frozen=True)
class Chunk:
    """One reviewable slice of a large diff: whole files, or one file's hunks split up."""

    number: int
    parts: list[tuple[str, str]]  # (path, diff text)

    @property
    def text(self) -> str:
        return "".join(body for _, body in self.parts)

    @property
    def paths(self) -> list[str]:
        return list(dict.fromkeys(path for path, _ in self.parts))


@dataclass(frozen=True)
class ChunkPlan:
    chunks: list[Chunk]
    unreviewed: list[str]  # files left out once the chunk budget ran out
    partial: list[str]  # files split across the budget, so only part was reviewed


def _priority(path: str) -> int:
    """Code first, then tests, then config and data, then docs."""
    name = path.rsplit("/", 1)[-1].lower()
    if _TEST_PATH.search(path):
        return 1
    if name.endswith(_CODE_SUFFIXES) or name in ("dockerfile", "makefile"):
        return 0
    if name.endswith(_DOC_SUFFIXES):
        return 3
    return 2


_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def _diff_lines(text: str) -> list[str]:
    """`text` split after each newline only, keeping the newlines."""
    return [line for line in re.split(r"(?<=\n)", text) if line]


def _split_hunk(hunk: str, limit: int) -> list[str]:
    """A hunk bigger than `limit` cut into smaller hunks, each with a header whose line
    numbers match its own lines, so findings in any piece still point at the right line."""
    lines = _diff_lines(hunk)
    m = _HUNK_HEADER.match(lines[0].rstrip("\n"))
    if not m:
        return [hunk]
    old, new, tail = int(m.group(1)), int(m.group(2)), m.group(3)
    pieces, body, old_n, new_n = [], [], 0, 0

    def flush():
        nonlocal old, new, body, old_n, new_n
        if body:
            pieces.append(f"@@ -{old},{old_n} +{new},{new_n} @@{tail}\n" + "".join(body))
            old, new = old + old_n, new + new_n
            body, old_n, new_n = [], 0, 0

    size = 0
    for line in lines[1:]:
        if body and size + len(line) > limit:
            flush()
            size = 0
        body.append(line)
        size += len(line)
        if line.startswith("-"):
            old_n += 1
        elif line.startswith("+"):
            new_n += 1
        elif not line.startswith("\\"):
            old_n += 1
            new_n += 1
    flush()
    return pieces


def _split_file(fd: FileDiff, limit: int) -> list[str]:
    """One file's diff in pieces under `limit`, cut at hunk boundaries (and inside a hunk
    that alone is too big), each piece keeping the file header so it reads on its own."""
    if len(fd.body) <= limit:
        return [fd.body]
    lines = _diff_lines(fd.body)
    first_hunk = next((i for i, ln in enumerate(lines) if ln.startswith("@@ ")), len(lines))
    header, hunks, current = "".join(lines[:first_hunk]), [], []
    for line in lines[first_hunk:]:
        if line.startswith("@@ ") and current:
            hunks.append("".join(current))
            current = []
        current.append(line)
    if current:
        hunks.append("".join(current))
    hunks = [part for h in hunks for part in _split_hunk(h, limit - len(header) - 200)]
    pieces, piece = [], ""
    for hunk in hunks:
        if piece and len(header) + len(piece) + len(hunk) > limit:
            pieces.append(header + piece)
            piece = ""
        piece += hunk
    if piece:
        pieces.append(header + piece)
    return pieces


def plan_chunks(
    files: list[FileDiff], limit: int = CHUNK_CHARS, max_chunks: int = MAX_CHUNKS
) -> ChunkPlan:
    """Pack file diffs into chunks under `limit` in `_priority` order. Within a tier, a file
    bigger than a whole chunk goes after the rest (it's often a bundle or a data table), and
    files sort by path so a directory's files stay together."""
    ordered = sorted(files, key=lambda fd: (_priority(fd.path), len(fd.body) > limit, fd.path))
    groups: list[list[tuple[str, str]]] = [[]]
    size = 0
    for fd in ordered:
        for piece in _split_file(fd, limit):
            if groups[-1] and size + len(piece) > limit:
                groups.append([])
                size = 0
            groups[-1].append((fd.path, piece))
            size += len(piece)
    kept, cut = groups[:max_chunks], groups[max_chunks:]
    chunks = [Chunk(number=i + 1, parts=g) for i, g in enumerate(kept) if g]
    in_kept = {path for g in kept for path, _ in g}
    in_cut = list(dict.fromkeys(path for g in cut for path, _ in g))
    return ChunkPlan(
        chunks=chunks,
        unreviewed=[p for p in in_cut if p not in in_kept],
        partial=[p for p in in_cut if p in in_kept],
    )


@dataclass(frozen=True)
class ReviewPayload:
    """The trimmed diff plus the full keep/drop manifest."""

    decisions: list[Decision]
    trimmed_diff: str
    forced_path: str | None = None
    base_ref: str | None = None

    @cached_property
    def chunk_plan(self) -> ChunkPlan | None:
        """How a diff too big for one read is split; None when it fits in one."""
        if len(self.trimmed_diff) <= CHUNK_CHARS:
            return None
        return plan_chunks(split_file_diffs(self.trimmed_diff))

    @property
    def kept(self) -> list[Decision]:
        return [d for d in self.decisions if d.kept]

    @property
    def dropped(self) -> list[Decision]:
        return [d for d in self.decisions if not d.kept]

    @property
    def kept_lines(self) -> int:
        return sum(d.added + d.removed for d in self.kept)

    @property
    def dropped_lines(self) -> int:
        return sum(d.added + d.removed for d in self.dropped)

    @property
    def design_docs(self) -> list[str]:
        return [fd.path for fd in split_file_diffs(self.trimmed_diff) if _is_design_doc(fd)]

    @property
    def lenses(self) -> list[str]:
        """Lens sub-agents the parallel path launches; empty on the small path. A chunked
        diff drops the second correctness pass: correctness runs once per chunk instead."""
        if self.path != "parallel":
            return []
        files = split_file_diffs(self.trimmed_diff)
        agentic = any(
            _AGENTIC_PATH.search(fd.path) or _AGENTIC_CODE.search(fd.body) for fd in files
        )
        base = [lens for lens in BASE_LENSES if not (self.chunk_plan and lens == "correctness-2")]
        return [
            *base,
            *(["agentic"] if agentic else []),
            *(["adr"] if self.design_docs else []),
        ]

    @property
    def path(self) -> str:
        if self.forced_path:
            return self.forced_path
        return "parallel" if self.kept_lines >= PARALLEL_THRESHOLD else "small"


def _is_design_doc(fd: FileDiff) -> bool:
    if _DESIGN_DOC_PATH.search(fd.path):
        return True
    if not fd.path.endswith(".md"):
        return False
    added = [line[1:].strip() for line in fd.body.splitlines() if line.startswith("+")]
    if any(line.startswith(("status:", "deciders:")) for line in added):
        return True
    nygard, *others = _DESIGN_DOC_HEADINGS
    if sum(h in added for h in nygard) >= 3:
        return True
    return any(all(h in added for h in group) for group in others)


def _run_git(args: list[str], repo: Path) -> str:
    # A diff can carry bytes that aren't UTF-8 (images git didn't mark binary, Latin-1
    # text); replacing them keeps the review going instead of crashing review-prep.
    out = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def split_file_diffs(diff_text: str) -> list[FileDiff]:
    """Split a unified diff into per-file sections with stats."""
    files: list[FileDiff] = []
    # Keep the leading "diff --git" on each chunk by splitting with a lookahead.
    chunks = re.split(r"(?m)^(?=diff --git )", diff_text)
    for chunk in chunks:
        if not chunk.strip():
            continue
        header = chunk.splitlines()[0]
        m = _DIFF_HEADER.match(header)
        if not m:
            continue
        # The b-side path is the post-change name (handles renames/adds); a delete
        # shows `+++ /dev/null`, in which case the a-side name is the right label.
        path = m.group(2)
        if "+++ /dev/null" in chunk:
            path = m.group(1)
        added = removed = 0
        has_hunks = False
        for line in _diff_lines(chunk):
            if line.startswith("@@ "):
                has_hunks = True
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        files.append(
            FileDiff(
                path=path,
                body=chunk if chunk.endswith("\n") else chunk + "\n",
                added=added,
                removed=removed,
                binary=bool(_BINARY.search(chunk)),
                has_hunks=has_hunks,
            )
        )
    return files


def classify(fd: FileDiff) -> tuple[bool, str]:
    """Return (keep, reason) for one file diff."""
    if fd.binary:
        return False, "binary"
    name = fd.path.rsplit("/", 1)[-1]
    if name in LOCKFILES:
        return False, "lockfile"
    parts = set(fd.path.split("/"))
    hit = parts & NOISE_DIR_PARTS
    if hit:
        return False, f"generated/vendored ({next(iter(hit))})"
    if fd.path.endswith(NOISE_SUFFIXES):
        return False, "minified/sourcemap"
    added = [line for line in _diff_lines(fd.body) if line[:1] == "+" and line[:3] != "+++"]
    if added and all(len(line) > MINIFIED_LINE_CHARS for line in added):
        return False, f"minified (every added line over {MINIFIED_LINE_CHARS:,} characters)"
    if fd.path.endswith(GENERATED_SUFFIXES):
        return False, "generated code"
    if not fd.has_hunks:
        return False, "no content change (rename/mode-only)"
    return True, "reviewable"


def _elide_long_lines(body: str) -> tuple[str, int]:
    """`body` with each added line over `MINIFIED_LINE_CHARS` replaced by a placeholder,
    one line for one so hunk line numbers still hold, and how many were replaced."""
    out, elided = [], 0
    for line in _diff_lines(body):
        if line[:1] == "+" and len(line) > MINIFIED_LINE_CHARS:
            line = f"+[line of {len(line) - 1:,} characters elided]\n"
            elided += 1
        out.append(line)
    return "".join(out), elided


def prepare_review(
    repo: Path | str = ".", base_branch: str | None = None, path: str | None = None
) -> ReviewPayload:
    """Produce the trimmed reviewable diff + keep/drop manifest for a branch."""
    repo = Path(repo).resolve()
    base_ref = diff_base(repo, base_branch)
    diff_text = _run_git(["diff", f"{base_ref}...HEAD"], repo)

    decisions: list[Decision] = []
    kept_bodies: list[str] = []
    for fd in split_file_diffs(diff_text):
        keep, reason = classify(fd)
        body = fd.body
        if keep:
            body, elided = _elide_long_lines(body)
            if elided:
                reason += f" ({elided} line(s) over {MINIFIED_LINE_CHARS:,} characters elided)"
            kept_bodies.append(body)
        decisions.append(
            Decision(path=fd.path, kept=keep, reason=reason, added=fd.added, removed=fd.removed)
        )
    return ReviewPayload(
        decisions=decisions,
        trimmed_diff="".join(kept_bodies),
        forced_path=path,
        base_ref=base_ref,
    )


def _detect_base(repo: Path) -> str:
    """The branch to diff against, per `klaussy.base_branch`.

    Stacked detection is off: it costs a merge base per branch, and nothing here
    can ask. The skills do that check.
    """
    return base_branch.resolve(Path(repo), detect_stacked=False).branch


def diff_base(repo: Path, explicit: str | None) -> str:
    """The ref to diff against. A base someone gave is used as-is; a resolved one prefers
    `origin/<base>`, since a stale local copy puts already-merged commits in the diff."""
    if explicit:
        return explicit
    resolved = base_branch.resolve(Path(repo), detect_stacked=False)
    if resolved.source == base_branch.SOURCE_EXPLICIT:
        return resolved.branch
    return base_branch.preferred_ref(repo, resolved.branch) or resolved.branch


def _chunk_command(payload: ReviewPayload, number: int | str) -> str:
    base = f" --base {payload.base_ref}" if payload.base_ref else ""
    return f"klaussy review-prep{base} --chunk {number}"


def render_chunk(payload: ReviewPayload, number: int) -> str:
    """One chunk's diff, with the rest of the change named so the reviewer knows its edges."""
    plan = payload.chunk_plan
    if plan is None:
        raise ValueError("this diff fits in one read; it has no chunks")
    if not 1 <= number <= len(plan.chunks):
        raise ValueError(f"chunk must be 1 to {len(plan.chunks)}, not {number}")
    chunk = plan.chunks[number - 1]
    base = f" --base {payload.base_ref}" if payload.base_ref else ""
    lines = [
        f"## Chunk {number} of {len(plan.chunks)}",
        "",
        "Review these files. The rest of the change is in the other chunks "
        f"(`klaussy review-prep{base} --summary` lists every file); read any of it a finding "
        "here depends on.",
        "",
        "```diff",
        chunk.text.rstrip("\n"),
        "```",
    ]
    return "\n".join(lines) + "\n"


def render_markdown(
    payload: ReviewPayload, *, summary_only: bool = False, chunk: int | None = None
) -> str:
    """Render the payload for injection into the review skill's context."""
    if chunk is not None:
        return render_chunk(payload, chunk)
    plan = payload.chunk_plan
    kept, dropped = payload.kept, payload.dropped
    lines: list[str] = []
    saved = payload.dropped_lines
    summary = (
        f"<!-- review-prep: {len(kept)} reviewable file(s), {payload.kept_lines} "
        f"changed line(s); dropped {len(dropped)} file(s) / {saved} line(s) of noise -->"
    )
    lines.append(summary)
    lines.append("")
    if payload.forced_path:
        reason = f"set by --path; {payload.kept_lines} reviewable lines"
    else:
        comparison = "≥" if payload.path == "parallel" else "<"
        reason = f"{payload.kept_lines} reviewable lines {comparison} {PARALLEL_THRESHOLD}"
    lines.append(f"**Review path: {payload.path}** ({reason})")
    docs = payload.design_docs
    if payload.lenses:
        lines.append("")
        lines.append(
            f"**Launch these {len(payload.lenses)} lens sub-agents in one message**, using the "
            "prompt in parallel.md, then send every finding through validation sub-agents. "
            "Don't review the diff yourself:"
        )
        for lens in payload.lenses:
            if plan and lens == "correctness":
                lines.append(
                    f"- correctness → `lens-correctness.md`, **once per chunk** "
                    f"({len(plan.chunks)} sub-agents): add `Review chunk <N> only.` to each prompt"
                )
                continue
            if lens == "correctness-2":
                lines.append(
                    "- correctness, second pass → `lens-correctness.md` "
                    "(add `This is the second correctness pass.` to its prompt)"
                )
                continue
            extra = f" (design docs: {', '.join(docs)})" if lens == "adr" else ""
            lines.append(f"- {lens} → `lens-{lens}.md`{extra}")
    elif docs:
        lines.append("")
        lines.append(f"**Design docs changed:** {', '.join(docs)}. Also apply `lens-adr.md`.")
    if plan and not summary_only:
        lines.append("")
        lines.append(f"## Too large to read at once: {len(plan.chunks)} chunks")
        lines.append("")
        lines.append(
            "The diff isn't printed here; one read would show only its start. Read each chunk "
            f"with `{_chunk_command(payload, '<N>')}`:"
        )
        lines.append("")
        for c in plan.chunks:
            lines.append(f"- Chunk {c.number}: {', '.join(f'`{p}`' for p in c.paths)}")
    elif not summary_only:
        lines.append("")
        lines.append("## Reviewable diff")
        lines.append("")
        if payload.trimmed_diff.strip():
            lines.append("```diff")
            lines.append(payload.trimmed_diff.rstrip("\n"))
            lines.append("```")
        else:
            lines.append("_No reviewable changes after trimming._")
    else:
        lines.append("")
        lines.append(f"## Reviewable files ({len(kept)})")
        lines.append("")
        for d in kept:
            lines.append(f"- `{d.path}` (+{d.added} / -{d.removed})")
    if dropped:
        lines.append("")
        lines.append(f"## Excluded from review ({len(dropped)} file(s))")
        lines.append("")
        lines.append("Dropped deterministically — skim only if a finding points here:")
        lines.append("")
        for d in dropped:
            lines.append(f"- `{d.path}` — {d.reason} (+{d.added} / -{d.removed})")
    if plan and (plan.unreviewed or plan.partial):
        lines.append("")
        lines.append(f"## Not reviewed: over the {MAX_CHUNKS}-chunk budget")
        lines.append("")
        lines.append(
            "Say in the review that these weren't covered; don't imply the review saw them:"
        )
        lines.append("")
        for p in plan.unreviewed:
            lines.append(f"- `{p}`")
        for p in plan.partial:
            lines.append(f"- `{p}` (partly: some of its hunks)")
    return "\n".join(lines) + "\n"


def render_dict(payload: ReviewPayload) -> dict:
    """Structured form of the payload (for `--json`)."""
    return {
        "kept": [
            {"path": d.path, "reason": d.reason, "added": d.added, "removed": d.removed}
            for d in payload.kept
        ],
        "dropped": [
            {"path": d.path, "reason": d.reason, "added": d.added, "removed": d.removed}
            for d in payload.dropped
        ],
        "kept_lines": payload.kept_lines,
        "dropped_lines": payload.dropped_lines,
        "path": payload.path,
        "lenses": payload.lenses,
        "design_docs": payload.design_docs,
        "chunks": [
            {"number": c.number, "paths": c.paths, "chars": len(c.text)}
            for c in (payload.chunk_plan.chunks if payload.chunk_plan else [])
        ],
        "unreviewed": payload.chunk_plan.unreviewed if payload.chunk_plan else [],
        "partial": payload.chunk_plan.partial if payload.chunk_plan else [],
        "trimmed_diff": payload.trimmed_diff,
    }
