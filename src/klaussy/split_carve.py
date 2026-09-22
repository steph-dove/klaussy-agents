"""Carve a large change into a stack of whole-file layers, then verify the stack.

The split-pr skill decides the seams; this does the mechanical part it used to
drive one git command per turn: branch each layer off the one below, take each
layer's files as they stand at the carve source, commit, prove the top of the
stack reproduces the source byte for byte, and run the project's checks on
every layer. Files that must be split by hunk across layers are carved by hand;
`verify_stack` then checks a hand-carved stack the same way.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PARENT_KEY = "klaussyparent"


class CarveError(RuntimeError):
    """A precondition or the carve itself failed; nothing half-built is left."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise CarveError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def _out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def _ok(repo: Path, *args: str) -> bool:
    return _git(repo, *args, check=False).returncode == 0


@dataclass
class Layer:
    branch: str
    message: str
    paths: list[str]


@dataclass
class CheckResult:
    layer: str
    command: str
    ok: bool
    tail: str  # last lines of output, for a failure


@dataclass
class StackReport:
    base: str
    tip: str
    layers: list[str]
    identical: bool
    differing: list[str] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.identical and all(c.ok for c in self.checks) and not self.warnings


def load_plan(path: Path) -> tuple[str, str, list[Layer]]:
    data = json.loads(Path(path).read_text())
    try:
        layers = [Layer(x["branch"], x["message"], list(x["paths"])) for x in data["layers"]]
        return data["base"], data["tip"], layers
    except (KeyError, TypeError) as exc:
        raise CarveError("plan needs base, tip, and layers of {branch, message, paths}") from exc


def _base_ref(repo: Path, base: str) -> str:
    for ref in (f"origin/{base}", base):
        if _ok(repo, "rev-parse", "--verify", "--quiet", ref):
            return ref
    raise CarveError(f"base {base!r} not found locally or on origin")


def _covers(path: str, file: str) -> bool:
    path = path.rstrip("/")
    return file == path or file.startswith(path + "/")


def assign_files(changed: list[str], layers: list[Layer]) -> dict[str, list[str]]:
    """Map each layer to its changed files; every file must land in exactly one."""
    owners: dict[str, list[str]] = {f: [] for f in changed}
    for layer in layers:
        for path in layer.paths:
            hits = [f for f in changed if _covers(path, f)]
            if not hits:
                raise CarveError(f"{layer.branch}: {path!r} matches no changed file")
            for f in hits:
                owners[f].append(layer.branch)
    unowned = sorted(f for f, o in owners.items() if not o)
    shared = sorted(f"{f} ({', '.join(o)})" for f, o in owners.items() if len(o) > 1)
    if unowned:
        raise CarveError(f"changed files in no layer: {', '.join(unowned)}")
    if shared:
        raise CarveError(
            "files in more than one layer (carve those layers by hand with "
            f"`git checkout -p`): {', '.join(shared)}"
        )
    return {layer.branch: [f for f in changed if owners[f] == [layer.branch]] for layer in layers}


def carve(repo: Path | str, base: str, tip: str, layers: list[Layer]) -> list[str]:
    """Create one branch per layer, bottom-up. Rolls back everything on failure."""
    repo = Path(repo).resolve()
    # Untracked files ride along safely (the plan file itself may be one).
    if _out(repo, "status", "--porcelain", "--untracked-files=no"):
        raise CarveError("the working tree is dirty; snapshot or stash it first")
    base_ref = _base_ref(repo, base)
    tip_sha = _out(repo, "rev-parse", "--verify", f"{tip}^{{commit}}")
    for layer in layers:
        if _ok(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{layer.branch}"):
            raise CarveError(f"branch {layer.branch} already exists")
    fork = _out(repo, "merge-base", base_ref, tip_sha)
    # --no-renames lists a rename as delete + add, so the old path is carved too.
    changed = _out(repo, "diff", "--name-only", "--no-renames", fork, tip_sha).splitlines()
    files = assign_files(changed, layers)

    original = _git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    original = original or _out(repo, "rev-parse", "HEAD")
    created: list[str] = []
    try:
        parent = fork
        for layer in layers:
            _git(repo, "checkout", "-q", "-b", layer.branch, parent)
            created.append(layer.branch)
            for f in files[layer.branch]:
                if _ok(repo, "cat-file", "-e", f"{tip_sha}:{f}"):
                    _git(repo, "checkout", tip_sha, "--", f)
                else:
                    _git(repo, "rm", "-q", "--ignore-unmatch", "--", f)
            # --no-verify: a formatting hook would edit the layer, and the carve
            # must reproduce the source exactly. The skill reports the bypass.
            _git(repo, "commit", "-q", "--no-verify", "-m", layer.message)
            parent = layer.branch
        for below, above in zip(created, created[1:]):
            _git(repo, "config", f"branch.{above}.{PARENT_KEY}", below)
    except CarveError as exc:
        stranded = []
        if _git(repo, "checkout", "-q", "--force", original, check=False).returncode != 0:
            stranded.append(f"could not check out {original} again")
        for b in created:
            if _git(repo, "branch", "-q", "-D", b, check=False).returncode != 0:
                stranded.append(b)
        if stranded:
            raise CarveError(f"{exc}; rollback left behind: {', '.join(stranded)}") from exc
        raise
    back = _git(repo, "checkout", "-q", original, check=False)
    if back.returncode != 0:
        raise CarveError(
            f"carved {', '.join(created)}, but could not check out {original} again "
            f"({back.stderr.strip()}); the worktree is on the top layer and the branches "
            "already exist, so fix the checkout rather than re-running the carve"
        )
    return created


def _run_check(repo: Path, command: str) -> tuple[bool, str]:
    # No shell either way. Windows takes the string as-is (CreateProcess does its
    # own quoting); POSIX needs it split, and non-POSIX shlex would keep quotes.
    argv: str | list[str] = command if os.name == "nt" else shlex.split(command)
    try:
        proc = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True)
    except FileNotFoundError:
        return False, f"command not found: {command.split()[0]}"
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
    return proc.returncode == 0, tail


def verify_stack(
    repo: Path | str, base: str, tip: str, layers: list[str], checks: list[str] | None = None
) -> StackReport:
    """Top layer must equal the carve source; each layer must pass each check."""
    repo = Path(repo).resolve()
    if checks and _out(repo, "status", "--porcelain", "--untracked-files=no"):
        raise CarveError("the working tree is dirty; checks need to switch branches")
    tip_sha = _out(repo, "rev-parse", "--verify", f"{tip}^{{commit}}")
    top = layers[-1]
    differing = _out(repo, "diff", "--name-status", tip_sha, top).splitlines()
    report = StackReport(base, tip_sha, layers, identical=not differing, differing=differing)
    if not checks:
        return report
    original = _git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    original = original or _out(repo, "rev-parse", "HEAD")
    try:
        for layer in layers:
            _git(repo, "checkout", "-q", layer)
            for command in checks:
                ok, tail = _run_check(repo, command)
                report.checks.append(CheckResult(layer, command, ok, "" if ok else tail))
    finally:
        # Leaving the user on a layer branch while reporting success hides the move.
        proc = _git(repo, "checkout", "-q", "--force", original, check=False)
        if proc.returncode != 0:
            report.warnings.append(f"still on {layers[-1]}: {proc.stderr.strip()}")
    return report


def render_report(report: StackReport) -> str:
    lines = [f"Stack on {report.base}, carved from {report.tip[:7]}:"]
    lines += [f"  {i}. {name}" for i, name in enumerate(report.layers, 1)]
    if report.identical:
        lines.append(f"Identity: {report.layers[-1]} matches the carve source exactly.")
    else:
        lines.append(f"Identity: FAILED, {report.layers[-1]} differs from the carve source in:")
        lines += [f"    {d}" for d in report.differing]
    for w in report.warnings:
        lines.append(f"WARNING: {w}")
    for c in report.checks:
        lines.append(f"{'pass' if c.ok else 'FAIL'} {c.layer}: {c.command}")
        if not c.ok:
            lines += [f"    {line}" for line in c.tail.splitlines()]
    return "\n".join(lines) + "\n"
