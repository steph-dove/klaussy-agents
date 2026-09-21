"""`klaussy split-carve` / `split-verify` against a real repository."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from klaussy import split_carve as carve
from klaussy.cli import app

runner = CliRunner()
PY = f'"{sys.executable}"'


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """main has old.py and keep.py; feat/big renames old.py, deletes keep.py, adds three files."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        _git(tmp_path, "config", key, value)
    (tmp_path / "old.py").write_text("x = 1\n")
    (tmp_path / "keep.py").write_text("y = 2\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "chore: base")
    _git(tmp_path, "checkout", "-q", "-b", "feat/big")
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "schema.py").write_text("SCHEMA = 1\n")
    (tmp_path / "api.py").write_text("from db.schema import SCHEMA\n")
    (tmp_path / "ui.py").write_text("import api\n")
    _git(tmp_path, "mv", "old.py", "renamed.py")
    _git(tmp_path, "rm", "-q", "keep.py")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "wip: pre-split snapshot")
    return tmp_path


LAYERS = [
    carve.Layer("feat/big-1-db", "feat(db): schema", ["db/", "old.py", "renamed.py"]),
    carve.Layer("feat/big-2-api", "feat(api): endpoint", ["api.py", "keep.py"]),
    carve.Layer("feat/big-3-ui", "feat(ui): screen", ["ui.py"]),
]


class TestCarve:
    def test_stack_reproduces_the_source(self, repo: Path):
        created = carve.carve(repo, "main", "feat/big", LAYERS)
        assert created == [layer.branch for layer in LAYERS]
        report = carve.verify_stack(repo, "main", "feat/big", created)
        assert report.identical, report.differing
        # Each layer holds only its own files, stacked on the one below.
        assert _git(repo, "diff", "--name-only", "feat/big-1-db", "feat/big-2-api").split() == [
            "api.py",
            "keep.py",
        ]
        assert _git(repo, "config", "branch.feat/big-3-ui.klaussyparent") == "feat/big-2-api"
        assert _git(repo, "branch", "--show-current") == "feat/big"

    def test_refuses_an_unassigned_file(self, repo: Path):
        layers = LAYERS[:2]
        with pytest.raises(carve.CarveError, match="in no layer: ui.py"):
            carve.carve(repo, "main", "feat/big", layers)
        assert not _git(repo, "branch", "--list", "feat/big-1-db")

    def test_refuses_a_file_in_two_layers(self, repo: Path):
        layers = [*LAYERS[:2], carve.Layer("feat/big-3-ui", "feat(ui)", ["ui.py", "api.py"])]
        with pytest.raises(carve.CarveError, match="checkout -p"):
            carve.carve(repo, "main", "feat/big", layers)

    def test_refuses_a_path_that_matches_nothing(self, repo: Path):
        layers = [*LAYERS, carve.Layer("feat/big-4", "x", ["nope/"])]
        with pytest.raises(carve.CarveError, match="matches no changed file"):
            carve.carve(repo, "main", "feat/big", layers)

    def test_refuses_an_existing_branch(self, repo: Path):
        _git(repo, "branch", "feat/big-2-api", "main")
        with pytest.raises(carve.CarveError, match="already exists"):
            carve.carve(repo, "main", "feat/big", LAYERS)

    def test_rolls_back_a_failed_carve(self, repo: Path):
        # An empty commit message makes git refuse the second layer's commit.
        layers = [LAYERS[0], carve.Layer("feat/big-2-api", "", ["api.py", "keep.py"]), LAYERS[2]]
        with pytest.raises(carve.CarveError):
            carve.carve(repo, "main", "feat/big", layers)
        assert not _git(repo, "branch", "--list", "feat/big-*")
        assert _git(repo, "branch", "--show-current") == "feat/big"
        assert not _git(repo, "status", "--porcelain")


class TestVerify:
    def test_detects_a_dropped_file(self, repo: Path):
        created = carve.carve(repo, "main", "feat/big", LAYERS)
        _git(repo, "checkout", "-q", "feat/big-3-ui")
        _git(repo, "rm", "-q", "ui.py")
        _git(repo, "commit", "-q", "-m", "oops")
        _git(repo, "checkout", "-q", "feat/big")
        report = carve.verify_stack(repo, "main", "feat/big", created)
        assert not report.identical
        assert any("ui.py" in d for d in report.differing)

    def test_runs_each_check_on_each_layer(self, repo: Path):
        created = carve.carve(repo, "main", "feat/big", LAYERS)
        # Passes only once ui.py exists, i.e. on the top layer.
        check = f"{PY} -c \"import os, sys; sys.exit(0 if os.path.exists('ui.py') else 1)\""
        report = carve.verify_stack(repo, "main", "feat/big", created, [check])
        assert [(c.layer, c.ok) for c in report.checks] == [
            ("feat/big-1-db", False),
            ("feat/big-2-api", False),
            ("feat/big-3-ui", True),
        ]
        assert not report.ok
        assert _git(repo, "branch", "--show-current") == "feat/big"


class TestFailureIsVisible:
    def test_a_stranded_carve_says_the_branches_exist(self, repo: Path, monkeypatch):
        # Silence here reads as a failed carve, and re-running hits "already exists".
        real = carve._git

        def fake(repo_path, *args, **kwargs):
            if args[:2] == ("checkout", "-q") and args[2:3] == ("feat/big",):
                return subprocess.CompletedProcess(args, 1, "", "cannot check out")
            return real(repo_path, *args, **kwargs)

        monkeypatch.setattr(carve, "_git", fake)
        with pytest.raises(carve.CarveError, match="branches already exist"):
            carve.carve(repo, "main", "feat/big", LAYERS)
        assert _git(repo, "branch", "--list", "feat/big-1-db")

    def test_a_stranded_checkout_fails_the_report(self, repo: Path):
        report = carve.StackReport("main", "abc1234", ["l1", "l2"], identical=True)
        report.warnings.append("still on l2: some git error")
        assert not report.ok
        assert "WARNING: still on l2" in carve.render_report(report)


class TestCli:
    def test_split_carve_end_to_end(self, repo: Path, tmp_path: Path):
        plan = tmp_path / "plan.json"
        plan.write_text(
            json.dumps(
                {
                    "base": "main",
                    "tip": "feat/big",
                    "layers": [
                        {"branch": x.branch, "message": x.message, "paths": x.paths} for x in LAYERS
                    ],
                }
            )
        )
        ok = f'{PY} -c "pass"'
        result = runner.invoke(app, ["split-carve", str(plan), "--check", ok, "-r", str(repo)])
        assert result.exit_code == 0, result.stdout
        assert "matches the carve source exactly" in result.stdout
        assert result.stdout.count("pass ") == 3

    def test_split_verify_fails_on_a_mismatch(self, repo: Path):
        carve.carve(repo, "main", "feat/big", LAYERS)
        args = ["split-verify", "--tip", "feat/big", "--layers", "feat/big-1-db,feat/big-2-api"]
        result = runner.invoke(app, [*args, "-r", str(repo)])
        assert result.exit_code == 1
        assert "Identity: FAILED" in result.stdout
