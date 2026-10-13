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
        "SINCE": "",
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
    assert "--timeout 1500" in args and "--since" not in args
    assert '"status": "x"' in result.stdout


def _fake_bin(tmp_path: Path, name: str, script: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / name).write_text("#!/bin/sh\n" + script)
    (bin_dir / name).chmod(0o755)
    return bin_dir


def _run_step(tmp_path: Path, name: str, bin_dir: Path, **env: str) -> subprocess.CompletedProcess:
    full = {
        **os.environ,
        "GITHUB_REPOSITORY": "me/app",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "out"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        **env,
    }
    return subprocess.run(
        ["bash", "-eo", "pipefail", "-c", _step(name)["run"]],
        cwd=tmp_path,
        env=full,
        capture_output=True,
        text=True,
    )


def test_the_last_review_lookup_takes_the_newest_klaussy_review(tmp_path):
    step = _step("Find the last klaussy review")
    assert "inputs.incremental == 'true'" in step["if"] and "GH_TOKEN" in step["env"]
    bin_dir = _fake_bin(tmp_path, "gh", 'printf "aaa111\\nbbb222\\n"\n')
    result = _run_step(tmp_path, "Find the last klaussy review", bin_dir, PR="7")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out").read_text().strip() == "since=bbb222"


def test_a_failed_lookup_means_a_full_review_not_a_failed_job(tmp_path):
    bin_dir = _fake_bin(tmp_path, "gh", "exit 1\n")
    result = _run_step(tmp_path, "Find the last klaussy review", bin_dir, PR="7")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out").read_text().strip() == "since="
    assert "::warning::Couldn't look up the last klaussy review" in result.stdout


def test_the_review_step_passes_the_last_reviewed_commit(tmp_path):
    bin_dir = _fake_bin(
        tmp_path,
        "klaussy",
        'echo "$@" > "$RUNNER_TEMP/args"\necho "{}" > "$RUNNER_TEMP/klaussy-result.json"\n',
    )
    env = {
        "AGENT": "claude",
        "BASE_REF": "main",
        "BUDGET": "20",
        "MODEL": "",
        "MAX_AI_CREDITS": "",
        "INCLUDE_NITS": "false",
        "ENRICH": "false",
        "SINCE": "abc1234",
        "REVIEW_TIMEOUT": "1500",
    }
    result = _run_step(tmp_path, "Review", bin_dir, **env)
    assert result.returncode == 0, result.stderr
    assert "--since abc1234" in (tmp_path / "args").read_text()


@pytest.mark.parametrize(("since", "flag"), [("abc1234def", "--since abc1234def"), (None, "")])
def test_posting_names_the_commit_the_review_started_from(tmp_path, since, flag):
    (tmp_path / "klaussy-result.json").write_text(
        '{"status": "ok", "since": %s}' % (f'"{since}"' if since else "null")
    )
    bin_dir = _fake_bin(
        tmp_path, "klaussy", 'echo "$@" >> "$RUNNER_TEMP/args"\necho \'{"body": "b"}\'\n'
    )
    _fake_bin(tmp_path, "gh", "exit 0\n")
    env = {"PR": "7", "EVENT": "COMMENT", "HEAD_SHA": "f" * 40}
    result = _run_step(tmp_path, "Post the review", bin_dir, **env)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "args").read_text().splitlines()
    assert len(calls) == 2
    assert all((flag in c) if flag else ("--since" not in c) for c in calls)


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


def test_a_headless_review_never_touches_the_callers_checkout(tmp_path, monkeypatch):
    repo = tmp_path / "app"
    repo.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@e.com"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    (repo / "CLAUDE.md").write_text("# Base\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "base"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True
    )
    (repo / ".claude" / "skills" / "mine").mkdir(parents=True)
    (repo / ".claude" / "skills" / "mine" / "SKILL.md").write_text("my own skill\n")
    (repo / "notes.md").write_text("uncommitted work\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(
        "#!/bin/sh\n"
        f"ls .claude/skills > {tmp_path}/skills.txt\n"
        'echo "**Verdict:** Approve" > REVIEW_OUTPUT.md\n'
        'echo \'{"session_id": "s", "total_cost_usd": 1}\'\n'
    )
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    result = CliRunner().invoke(
        app,
        [
            "review",
            "--headless",
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--out",
            str(tmp_path / "result.json"),
            "--diff-out",
            str(tmp_path / "pr.diff"),
            "--work-dir",
            str(tmp_path / "w"),
            "--repo-name",
            "My_App",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "w" / "REVIEW_OUTPUT.md").read_text() == "**Verdict:** Approve\n"
    assert "my-app-review" in (tmp_path / "skills.txt").read_text().split()
    assert (repo / ".claude/skills/mine/SKILL.md").read_text() == "my own skill\n"
    assert (repo / "notes.md").read_text() == "uncommitted work\n"
    assert not (repo / "REVIEW_OUTPUT.md").exists()
    worktrees = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list"], capture_output=True, text=True
    ).stdout
    assert len(worktrees.strip().splitlines()) == 1
