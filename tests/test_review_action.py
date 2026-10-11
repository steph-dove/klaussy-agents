import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from klaussy.cli import app

ACTION = Path(__file__).parent.parent / "actions" / "review" / "action.yml"


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text())


def _scripts() -> str:
    return "\n".join(s.get("run", "") for s in _action()["runs"]["steps"])


def test_action_is_a_composite_with_marketplace_metadata():
    action = _action()
    assert action["runs"]["using"] == "composite"
    assert action["name"] and action["description"] and action["branding"]


def test_every_klaussy_subcommand_the_action_calls_exists():
    used = set(re.findall(r"^\s*klaussy ([a-z][a-z-]+)", _scripts(), re.MULTILINE))
    assert used >= {"init", "skills", "review-post"}
    for command in used:
        assert CliRunner().invoke(app, [command, "--help"]).exit_code == 0, command


@pytest.mark.parametrize(
    ("has_key", "head_repo", "code", "run"),
    [
        ("true", "me/app", 0, "run=true"),
        ("false", "someone/fork", 0, "run=false"),
        ("false", "me/app", 1, ""),
    ],
)
def test_gate_skips_forks_but_fails_a_same_repo_pr_with_no_credential(
    tmp_path, has_key, head_repo, code, run
):
    gate = next(s for s in _action()["runs"]["steps"] if s.get("id") == "gate")
    output = tmp_path / "out"
    output.touch()
    env = {
        **os.environ,
        "HAS_KEY": has_key,
        "PR": "7",
        "HEAD_REPO": head_repo,
        "BASE_REPO": "me/app",
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(["bash", "-c", gate["run"]], env=env, capture_output=True, text=True)
    assert result.returncode == code, result.stdout
    assert output.read_text().strip() == run


def test_the_reviewer_never_gets_the_github_token_or_a_permission_bypass():
    for step in _action()["runs"]["steps"]:
        env = step.get("env", {})
        if "claude -p" in step.get("run", ""):
            assert "GH_TOKEN" not in env and "GITHUB_TOKEN" not in env
            assert "bypassPermissions" not in step["run"]
            assert "disableAllHooks" in step["run"]
