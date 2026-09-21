"""`klaussy restack` against real repositories: a bare origin plus a working clone."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from klaussy import restack
from klaussy.cli import app

runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    (repo / path).write_text(content)
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        _git(work, "config", key, value)
    _git(work, "remote", "add", "origin", str(origin))
    _commit(work, "base.txt", "base\n", "chore: base")
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def _stack(repo: Path) -> None:
    """main -> feat/a -> feat/b -> feat/c, one file per layer."""
    _git(repo, "checkout", "-q", "-b", "feat/a")
    _commit(repo, "a.txt", "a\n", "feat: a")
    _git(repo, "checkout", "-q", "-b", "feat/b")
    _commit(repo, "b.txt", "b\n", "feat: b")
    _git(repo, "checkout", "-q", "-b", "feat/c")
    _commit(repo, "c.txt", "c\n", "feat: c")


def _move_main(repo: Path, path: str = "main.txt", content: str = "moved\n") -> None:
    _git(repo, "checkout", "-q", "main")
    _commit(repo, path, content, "chore: move main")
    _git(repo, "push", "-q", "origin", "main")


def _run(repo: Path, chain: list[str]) -> restack.RunState:
    restack.start_run(repo, chain, base="main")
    return restack.advance(repo)


class TestPlan:
    def test_maps_a_linear_stack_bottom_up(self, repo: Path):
        _stack(repo)
        plan = restack.plan_restack(repo, base="main")
        assert [(b.name, b.parent) for b in plan.branches] == [
            ("feat/a", None),
            ("feat/b", "feat/a"),
            ("feat/c", "feat/b"),
        ]
        assert "klaussy restack run --chain feat/a,feat/b,feat/c" in restack.render_plan(plan)

    def test_flags_a_squash_landed_bottom(self, repo: Path):
        _stack(repo)
        # A squash merge puts a's content on main under a new SHA.
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "a.txt", "a\n", "feat: a (#1)")
        _git(repo, "push", "-q", "origin", "main")
        plan = restack.plan_restack(repo, base="main")
        landed = {b.name: b.landed for b in plan.branches}
        assert landed["feat/a"] == "squash"
        assert landed["feat/b"] is None

    def test_reports_a_dirty_tree_and_aliases(self, repo: Path):
        _stack(repo)
        _git(repo, "branch", "feat/c-copy", "feat/c")
        (repo / "base.txt").write_text("edited\n")
        plan = restack.plan_restack(repo, base="main")
        text = restack.render_plan(plan)
        assert "BLOCKED" in text
        assert ["feat/c", "feat/c-copy"] in plan.aliases


class TestRun:
    def test_rebases_each_branch_onto_its_new_parent(self, repo: Path):
        _stack(repo)
        _move_main(repo)
        state = _run(repo, ["feat/a", "feat/b", "feat/c"])
        assert state.done == ["feat/a", "feat/b", "feat/c"]
        main = _git(repo, "rev-parse", "origin/main")
        assert _git(repo, "merge-base", "feat/a", "origin/main") == main
        # Each child carries only its own commit: nothing replayed twice.
        for parent, child in (("feat/a", "feat/b"), ("feat/b", "feat/c")):
            assert _git(repo, "rev-list", "--count", f"{parent}..{child}") == "1"
        assert all(c.ok for c in restack.verify(repo))
        assert _git(repo, "config", "branch.feat/c.klaussyparent") == "feat/b"

    def test_amended_parent_does_not_replay_its_old_commit(self, repo: Path):
        # Unchanged parents hide a wrong boundary (git skips identical patches);
        # an amended one doesn't, so this is the case that pins `--onto <old tip>`.
        _stack(repo)
        _git(repo, "checkout", "-q", "feat/a")
        (repo / "a.txt").write_text("a, amended\n")
        _git(repo, "commit", "-q", "-a", "--amend", "-m", "feat: a")
        state = _run(repo, ["feat/a", "feat/b", "feat/c"])
        assert state.current is None, "replayed the parent's old commit and conflicted"
        assert _git(repo, "rev-list", "--count", "feat/a..feat/b") == "1"
        assert _git(repo, "show", "feat/c:a.txt") == "a, amended"

    def test_drops_a_squash_landed_parent(self, repo: Path):
        _stack(repo)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "a.txt", "a\n", "feat: a (#1)")
        _git(repo, "push", "-q", "origin", "main")
        state = _run(repo, ["feat/a", "feat/b", "feat/c"])
        assert "feat/a" in state.landed and "feat/a" not in state.done
        assert _git(repo, "rev-list", "--count", "origin/main..feat/b") == "1"
        assert all(c.ok for c in restack.verify(repo))

    def test_stops_on_a_conflict_and_continues(self, repo: Path):
        _stack(repo)
        _move_main(repo, "b.txt", "main's b\n")
        state = _run(repo, ["feat/a", "feat/b", "feat/c"])
        assert state.current == "feat/b"
        assert restack.conflicted_files(repo) == ["b.txt"]
        (repo / "b.txt").write_text("b\n")
        _git(repo, "add", "b.txt")
        _git(repo, "-c", "core.editor=true", "rebase", "--continue")
        state = restack.advance(repo)
        assert state.done == ["feat/a", "feat/b", "feat/c"]
        assert _git(repo, "rev-list", "--count", "feat/b..feat/c") == "1"
        # The resolved commit differs from the original, and verify says so.
        changed = {c.branch: c.changed for c in restack.verify(repo)}
        assert changed["feat/b"] and not changed["feat/c"]

    def test_continue_refuses_an_aborted_rebase(self, repo: Path):
        _stack(repo)
        _move_main(repo, "b.txt", "main's b\n")
        _run(repo, ["feat/a", "feat/b", "feat/c"])
        _git(repo, "rebase", "--abort")
        with pytest.raises(restack.RestackError, match="aborted"):
            restack.advance(repo)

    def test_undo_restores_every_tip(self, repo: Path):
        _stack(repo)
        before = {b: _git(repo, "rev-parse", b) for b in ("feat/a", "feat/b", "feat/c")}
        _move_main(repo, "b.txt", "main's b\n")
        _run(repo, ["feat/a", "feat/b", "feat/c"])
        restack.undo(repo)
        assert {b: _git(repo, "rev-parse", b) for b in before} == before
        with pytest.raises(restack.RestackError, match="no restack in progress"):
            restack.load_state(repo)

    def test_refuses_a_dirty_tree(self, repo: Path):
        _stack(repo)
        (repo / "c.txt").write_text("uncommitted\n")
        with pytest.raises(restack.RestackError, match="dirty"):
            restack.start_run(repo, ["feat/a", "feat/b", "feat/c"], base="main")

    def test_refuses_a_child_before_its_parent(self, repo: Path):
        _stack(repo)
        with pytest.raises(restack.RestackError, match="must come before"):
            restack.start_run(repo, ["feat/b", "feat/a"], base="main")


class TestFailureIsVisible:
    def test_a_failed_fetch_is_reported_not_swallowed(self, repo: Path):
        # Planning against stale refs picks the wrong base and nobody notices.
        _stack(repo)
        _git(repo, "remote", "add", "broken", str(repo / "nope.git"))
        plan = restack.plan_restack(repo, base="main")
        assert plan.fetch_failed
        assert "WARNING: `git fetch` failed" in restack.render_plan(plan)

    def test_an_unusable_squash_check_is_reported(self, repo: Path, monkeypatch):
        # `merge-tree --write-tree` needs git 2.38; older git can't spot a squash merge.
        _stack(repo)
        real = restack._git

        def fake(repo_path, *args, **kwargs):
            if args[:1] == ("merge-tree",):
                return subprocess.CompletedProcess(args, 129, "", "unknown option")
            return real(repo_path, *args, **kwargs)

        monkeypatch.setattr(restack, "_git", fake)
        plan = restack.plan_restack(repo, base="main", fetch=False)
        assert plan.squash_check_failed
        assert "needs git 2.38" in restack.render_plan(plan)

    def test_undo_works_after_a_run_that_warned(self, repo: Path):
        # The warning is already in the saved state; undo must not re-raise it.
        _stack(repo)
        _move_main(repo)
        _git(repo, "checkout", "-q", "-b", "scratch")
        restack.start_run(repo, ["feat/a", "feat/b", "feat/c"], base="main")
        _git(repo, "branch", "-m", "scratch", "scratch-renamed")
        assert restack.advance(repo).warnings
        _git(repo, "checkout", "-q", "scratch-renamed")
        _git(repo, "branch", "-m", "scratch-renamed", "scratch")
        state = restack.undo(repo)
        assert _git(repo, "rev-parse", "feat/c") == state.old_tip["feat/c"]

    def test_losing_the_original_branch_is_recorded(self, repo: Path):
        _stack(repo)
        _move_main(repo)
        _git(repo, "checkout", "-q", "-b", "scratch")
        restack.start_run(repo, ["feat/a", "feat/b", "feat/c"], base="main")
        # The branch we started on disappears while the rebases run.
        _git(repo, "branch", "-m", "scratch", "scratch-renamed")
        state = restack.advance(repo)
        assert any("scratch" in w for w in state.warnings), state.warnings
        assert restack.load_state(repo).warnings == state.warnings


class TestPush:
    def test_pushes_bottom_up_with_a_lease(self, repo: Path):
        _stack(repo)
        for b in ("feat/a", "feat/b", "feat/c"):
            _git(repo, "push", "-q", "origin", b)
        _move_main(repo)
        _run(repo, ["feat/a", "feat/b", "feat/c"])
        results = restack.push(repo)
        assert [(name, ok) for name, ok, _ in results] == [
            ("feat/a", True),
            ("feat/b", True),
            ("feat/c", True),
        ]
        assert _git(repo, "rev-parse", "origin/feat/c") == _git(repo, "rev-parse", "feat/c")

    def test_stops_when_the_lease_is_refused(self, repo: Path, tmp_path: Path):
        _stack(repo)
        for b in ("feat/a", "feat/b", "feat/c"):
            _git(repo, "push", "-q", "origin", b)
        # A teammate pushes to feat/a behind our back.
        other = tmp_path / "other"
        subprocess.run(["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], check=True)
        _git(other, "config", "user.name", "Mate")
        _git(other, "config", "user.email", "mate@example.com")
        _git(other, "checkout", "-q", "feat/a")
        _commit(other, "mate.txt", "mine\n", "feat: teammate work")
        _git(other, "push", "-q", "origin", "feat/a")
        _move_main(repo)
        _run(repo, ["feat/a", "feat/b", "feat/c"])
        results = restack.push(repo)
        assert results[0][0] == "feat/a" and results[0][1] is False
        assert len(results) == 1  # stopped: nothing above it was pushed


class TestCli:
    def test_full_cycle_through_the_cli(self, repo: Path):
        _stack(repo)
        for b in ("feat/a", "feat/b", "feat/c"):
            _git(repo, "push", "-q", "origin", b)
        _move_main(repo)
        r = str(repo)
        plan = runner.invoke(app, ["restack", "plan", "-r", r, "-b", "main"])
        assert plan.exit_code == 0 and "--chain feat/a,feat/b,feat/c" in plan.stdout
        chain = "feat/a,feat/b,feat/c"
        run = runner.invoke(app, ["restack", "run", "--chain", chain, "-r", r, "-b", "main"])
        assert run.exit_code == 0, run.stdout
        assert runner.invoke(app, ["restack", "verify", "-r", r]).exit_code == 0
        pushed = runner.invoke(app, ["restack", "push", "-r", r])
        assert pushed.exit_code == 0 and pushed.stdout.count("pushed") == 3

    def test_conflict_exits_2_with_next_steps(self, repo: Path):
        _stack(repo)
        _move_main(repo, "b.txt", "main's b\n")
        args = ["restack", "run", "--chain", "feat/a,feat/b,feat/c", "-r", str(repo), "-b", "main"]
        run = runner.invoke(app, args)
        assert run.exit_code == 2
        assert "CONFLICT rebasing feat/b in: b.txt" in run.stdout
        assert "klaussy restack run --continue" in run.stdout
