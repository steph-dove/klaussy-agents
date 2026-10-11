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


def _step(name: str) -> dict:
    return next(s for s in _action()["runs"]["steps"] if s["name"] == name)


def _gate(tmp_path: Path, **env: str) -> tuple[subprocess.CompletedProcess, str]:
    output = tmp_path / "out"
    output.touch()
    defaults = {
        "AGENT": "claude",
        "EVENT": "COMMENT",
        "HAS_CLAUDE_KEY": "false",
        "HAS_COPILOT_KEY": "false",
        "HAS_OPENAI_KEY": "false",
        "PR": "7",
        "HEAD_REPO": "me/app",
        "BASE_REPO": "me/app",
        "ACTOR": "someone",
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        ["bash", "-c", _step("Check the event and credentials")["run"]],
        env={**os.environ, **defaults, **env},
        capture_output=True,
        text=True,
    )
    return result, output.read_text().strip()


def test_action_is_a_composite_with_marketplace_metadata():
    action = _action()
    assert action["runs"]["using"] == "composite"
    assert action["name"] and action["description"] and action["branding"]


def test_every_klaussy_subcommand_the_action_calls_exists():
    used = set(re.findall(r"^\s*klaussy ([a-z][a-z-]+)", _scripts(), re.MULTILINE))
    assert used >= {"review", "review-post"}
    for command in used:
        assert CliRunner().invoke(app, [command, "--help"]).exit_code == 0, command


@pytest.mark.parametrize(
    ("env", "code", "run"),
    [
        ({"AGENT": "claude", "HAS_CLAUDE_KEY": "true"}, 0, "run=true"),
        ({"AGENT": "copilot", "HAS_COPILOT_KEY": "true"}, 0, "run=true"),
        ({"AGENT": "openai", "HAS_OPENAI_KEY": "true"}, 0, "run=true"),
        ({"AGENT": "copilot", "HAS_CLAUDE_KEY": "true"}, 1, ""),
        ({"AGENT": "openai", "HAS_CLAUDE_KEY": "true"}, 1, ""),
        ({"AGENT": "codex", "HAS_OPENAI_KEY": "true"}, 1, ""),
        ({"HEAD_REPO": "someone/fork"}, 0, "run=false"),
        ({"ACTOR": "dependabot[bot]"}, 0, "run=false"),
        ({}, 1, ""),
        ({"AGENT": "gemini", "HAS_CLAUDE_KEY": "true"}, 1, ""),
    ],
)
def test_gate_checks_the_chosen_agents_credential_and_skips_forks(tmp_path, env, code, run):
    result, output = _gate(tmp_path, **env)
    assert result.returncode == code, result.stdout
    assert output == run


def test_gate_rejects_an_unknown_event_before_the_review_runs(tmp_path):
    result, _ = _gate(tmp_path, HAS_CLAUDE_KEY="true", EVENT="request_changes")
    assert result.returncode == 1 and "event must be" in result.stdout


def test_the_review_step_runs_the_shared_runner_without_a_write_token():
    review = _step("Review")
    assert "GH_TOKEN" not in review["env"] and "GITHUB_TOKEN" not in review["env"]
    assert "unset GH_TOKEN GITHUB_TOKEN" in review["run"]
    assert "klaussy review" in review["run"] and "--headless" in review["run"]
    for bypass in ("bypassPermissions", "--allow-all", "--yolo", "danger-full-access"):
        assert bypass not in _scripts(), bypass


def test_steps_that_run_python_in_the_checkout_keep_it_off_sys_path():
    for name in ("Install klaussy and the agent", "Review", "Post the review"):
        assert _step(name)["env"].get("PYTHONSAFEPATH") == "1", name
    install = _step("Install klaussy and the agent")["run"]
    assert install.lstrip().startswith("# Run from outside the checkout")
    assert 'cd "$RUNNER_TEMP"' in install


def test_posting_redacts_every_agents_credential():
    env = _step("Post the review")["env"]
    for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "COPILOT_GITHUB_TOKEN"):
        assert name in env, name
    assert "OPENAI_API_KEY" in env


@pytest.mark.parametrize(("code", "step_code"), [(0, 0), (1, 1)])
def test_the_review_step_fails_when_the_runner_does(tmp_path, code, step_code):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "klaussy"
    fake.write_text(
        "#!/bin/sh\n"
        'echo "$@" > "$RUNNER_TEMP/args"\n'
        'echo \'{"status": "x"}\' > "$RUNNER_TEMP/klaussy-result.json"\n'
        f"exit {code}\n"
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "AGENT": "openai",
        "BASE_REF": "main",
        "BUDGET": "20",
        "MODEL": "",
        "MAX_AI_CREDITS": "",
        "INCLUDE_NITS": "true",
        "ENRICH": "false",
        "REVIEW_TIMEOUT": "1500",
        "GITHUB_REPOSITORY": "me/My_App",
        "RUNNER_TEMP": str(tmp_path),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", _step("Review")["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == step_code, result.stdout + result.stderr
    args = (tmp_path / "args").read_text()
    assert "review --headless" in args and "--agent openai" in args
    assert "--base origin/main" in args and "--repo-name My_App" in args
    assert "--include-nits" in args and "--enrich" not in args
    assert "--timeout 1500" in args
    assert '"status": "x"' in result.stdout


def test_the_cli_writes_a_result_even_when_the_out_dir_is_missing(tmp_path):
    out = tmp_path / "nested" / "result.json"
    result = CliRunner().invoke(
        app,
        [
            "review",
            "--headless",
            "--repo",
            str(tmp_path),
            "--base",
            "origin/main",
            "--out",
            str(out),
            "--diff-out",
            str(tmp_path / "d" / "pr.diff"),
            "--work-dir",
            str(tmp_path / "w"),
        ],
    )
    assert result.exit_code == 1
    assert '"status": "error"' in out.read_text()


def test_the_review_timeout_fits_inside_the_job_timeout():
    default = int(_action()["inputs"]["review-timeout"]["default"])
    workflow = yaml.safe_load(
        (ACTION.parents[2] / ".github/workflows/klaussy-review.yml").read_text()
    )
    for name, job in workflow["jobs"].items():
        assert default < job["timeout-minutes"] * 60, name
