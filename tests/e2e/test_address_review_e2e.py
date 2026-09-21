"""address-review, driven for real against a recording `gh`.

The prompt eval could only ask what commands the agent *would* run. What matters
is what it does: that it reads all three feedback sources rather than the inline
comments alone, that every read is paginated, that the fix lands in the file,
and that nothing is posted until the reply has been through the humanize skill.

Costs one real agent run; see e2e_harness.py for the gate.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import e2e_harness as harness
import pytest

SKILL = "address-review"

# A `gh` that records every call and answers the three read endpoints. The
# payloads live inside the script, and the script lives outside the repo's
# directory tree: an agent that can read a fixture file will read it instead of
# calling `gh`, and then the test stops observing the thing it was written for.
GH_SHIM = """#!/bin/bash
echo "$@" >> "$GH_LOG"
inline='[{"id":991,"path":"src/api/session.py","line":12,"user":{"login":"marco"},
  "body":"retry() swallows the final HTTPError instead of re-raising it."}]'
reviews='[{"id":77,"user":{"login":"marco"},"state":"CHANGES_REQUESTED","body":"One fix."}]'
conversation='[{"id":1201,"user":{"login":"priya"},
  "body":"Also please rename tmp to response in that function."}]'
case "$*" in
  --version) echo "gh version 2.63.0 (2026-01-01)" ;;
  *"auth status"*) echo "github.com: Logged in to github.com account dev (keyring)" ;;
  *"repo view"*) echo '{"name":"shop","owner":{"login":"acme"}}' ;;
  *"pulls/42/comments"*) echo "$inline" ;;
  *"pulls/42/reviews"*) echo "$reviews" ;;
  *"issues/42/comments"*) echo "$conversation" ;;
  *"pr view"*) echo '{"number":42,"headRefName":"fix/retry","baseRefName":"main"}' ;;
  *"--method POST"*|*"pr comment"*) echo '{"id":9001,"html_url":"http://x.invalid/9001"}' ;;
  *) echo '[]' ;;
esac
"""

SOURCE = """import requests


def retry(url):
    for attempt in range(3):
        try:
            tmp = requests.get(url)
            return tmp
        except requests.HTTPError:
            continue
    return None
"""


def _build(tmp_path: Path, attempt: int) -> Path:
    """A fresh repo per attempt: the second run must not inherit the first's fix."""
    root = tmp_path / f"attempt{attempt}"
    root.mkdir()
    work = root / "shop"
    (work / "src" / "api").mkdir(parents=True)
    (work / "src" / "api" / "session.py").write_text(SOURCE)
    (work / "CLAUDE.md").write_text("# shop\n\n## Commands\n\n```bash\npytest\n```\n")
    harness.git(work.parent, "init", "-q", "-b", "main", str(work))
    for key, value in (("user.name", "Dev"), ("user.email", "dev@example.com")):
        harness.git(work, "config", key, value)
    harness.git(work, "add", ".")
    harness.git(work, "commit", "-q", "-m", "chore: base")
    # Without a remote the skill correctly stops and asks for a paste instead.
    remote = root / "origin.git"
    harness.git(work, "init", "-q", "--bare", str(remote))
    harness.git(work, "remote", "add", "origin", str(remote))
    harness.git(work, "push", "-q", "-u", "origin", "main")
    harness.git(work, "checkout", "-q", "-b", "fix/retry")
    harness.install_skills(work)
    return work


@pytest.fixture()
def fake_gh(monkeypatch):
    """A `gh` on PATH that logs its arguments, kept well away from the repo."""
    home = Path(tempfile.mkdtemp(prefix="klaussy-gh-"))
    gh = home / "gh"
    gh.write_text(GH_SHIM)
    gh.chmod(0o755)
    log = home / "gh.log"
    log.touch()
    monkeypatch.setenv("GH_LOG", str(log))
    yield home, log
    shutil.rmtree(home, ignore_errors=True)


def _check_one_run(repo: Path, bin_dir: Path, log: Path) -> None:
    """Drive one run and assert on it; raises AssertionError if the run fell short."""
    log.write_text("")
    calls, final = harness.run_agent(
        repo,
        "Use the shop-address-review skill to address the feedback on PR 42, end to end.",
        path_prefix=bin_dir,
    )
    gh_calls = log.read_text()
    trace = f"gh calls:\n{gh_calls}\ntool calls:\n" + "\n".join(calls) + f"\nagent said:\n{final}"

    # Every feedback source, every page.
    for endpoint in ("pulls/42/comments", "pulls/42/reviews", "issues/42/comments"):
        reads = [line for line in gh_calls.splitlines() if endpoint in line]
        assert reads, f"never read {endpoint}. {trace}"
        assert any("--paginate" in r for r in reads), (
            f"every read of {endpoint} was unpaginated, so page 2 is lost. {trace}"
        )

    # The fix the inline comment asked for actually landed.
    source = (repo / "src" / "api" / "session.py").read_text()
    assert "raise" in source, f"the swallowed error was never re-raised:\n{source}"

    # Nothing posts before the humanize pass. `gh api ... -f body=` is a POST.
    posted = [i for i, c in enumerate(calls) if "pr comment" in c or "body=" in c]
    humanized = [i for i, c in enumerate(calls) if "humanize" in c.lower()]
    assert posted, f"no reply was posted. {trace}"
    assert humanized, f"the reply never went through humanize. {trace}"
    assert min(humanized) < min(posted), f"posted before humanizing. {trace}"


@harness.requires_e2e
def test_reads_every_source_and_humanizes_before_posting(tmp_path: Path, fake_gh):
    """One retry, each on a fresh repo: a broken skill fails both."""
    bin_dir, log = fake_gh
    try:
        _check_one_run(_build(tmp_path, 1), bin_dir, log)
    except AssertionError as first:
        try:
            _check_one_run(_build(tmp_path, 2), bin_dir, log)
        except AssertionError as second:
            raise AssertionError(f"both attempts fell short.\n\nfirst:\n{first}") from second
