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
in. The expensive half (prompt-caching the diff across parallel sub-agents,
model-tiering the lenses) lives in the skill/orchestration layer, not here.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
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
class ReviewPayload:
    """The trimmed diff plus the full keep/drop manifest."""

    decisions: list[Decision]
    trimmed_diff: str
    forced_path: str | None = None

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
        """Lens sub-agents the parallel path launches; empty on the small path."""
        if self.path != "parallel":
            return []
        files = split_file_diffs(self.trimmed_diff)
        agentic = any(
            _AGENTIC_PATH.search(fd.path) or _AGENTIC_CODE.search(fd.body) for fd in files
        )
        return [
            *BASE_LENSES,
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
    out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
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
        for line in chunk.splitlines():
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
    if fd.path.endswith(GENERATED_SUFFIXES):
        return False, "generated code"
    if not fd.has_hunks:
        return False, "no content change (rename/mode-only)"
    return True, "reviewable"


def prepare_review(
    repo: Path | str = ".", base_branch: str | None = None, path: str | None = None
) -> ReviewPayload:
    """Produce the trimmed reviewable diff + keep/drop manifest for a branch."""
    repo = Path(repo).resolve()
    base = base_branch or _detect_base(repo)
    diff_text = _run_git(["diff", f"{base}...HEAD"], repo)

    decisions: list[Decision] = []
    kept_bodies: list[str] = []
    for fd in split_file_diffs(diff_text):
        keep, reason = classify(fd)
        decisions.append(
            Decision(path=fd.path, kept=keep, reason=reason, added=fd.added, removed=fd.removed)
        )
        if keep:
            kept_bodies.append(fd.body)
    return ReviewPayload(decisions=decisions, trimmed_diff="".join(kept_bodies), forced_path=path)


def _detect_base(repo: Path) -> str:
    """The branch to diff against, per `klaussy.base_branch`.

    Stacked detection is off: it costs a merge base per branch, and nothing here
    can ask. The skills do that check.
    """
    return base_branch.resolve(Path(repo), detect_stacked=False).branch


def render_markdown(payload: ReviewPayload, *, summary_only: bool = False) -> str:
    """Render the payload for injection into the review skill's context."""
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
    if not summary_only:
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
        "trimmed_diff": payload.trimmed_diff,
    }
