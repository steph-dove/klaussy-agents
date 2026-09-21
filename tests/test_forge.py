"""Forge detection, the {{FORGE}} adapter block, and the permissions that match it."""

import json
import subprocess
from pathlib import Path

import pytest

from klaussy.agents.backends import _shell_prefixes
from klaussy.agents.base import build_skill_payloads
from klaussy.forge import (
    FORGE_BITBUCKET,
    FORGE_GITHUB,
    FORGE_GITLAB,
    FORGE_UNKNOWN,
    FORGES,
    detect_forge,
    detect_forge_cli,
    forge_block,
    forge_cli,
    forge_sections,
)
from klaussy.settings import _build_allowed_tools, generate_settings
from klaussy.skills import sanitize_skill_namespace, scaffold_skills

# Skills carrying the full adapter block. The rest reference a host only in
# passing, so injecting 20 lines of commands into them would be dead weight.
FORGE_SKILLS = ["restack", "address-review", "rest-of-the-owl"]


def _git_repo(path: Path, remote: str | None = None, name: str = "origin") -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", name, remote], check=True)
    return path


class TestDetection:
    @pytest.mark.parametrize(
        ("remote", "expected"),
        [
            ("git@github.com:owner/repo.git", FORGE_GITHUB),
            ("https://github.com/owner/repo.git", FORGE_GITHUB),
            ("ssh://git@github.acme.com:22/owner/repo.git", FORGE_GITHUB),
            ("git@gitlab.com:group/sub/repo.git", FORGE_GITLAB),
            ("https://gitlab.acme.io/group/repo", FORGE_GITLAB),
            ("git@bitbucket.org:workspace/repo.git", FORGE_BITBUCKET),
            ("https://stash.acme.com/scm/proj/repo.git", FORGE_BITBUCKET),
            ("git@git.acme.com:team/repo.git", FORGE_UNKNOWN),
            ("/srv/git/bare-repo.git", FORGE_UNKNOWN),
        ],
    )
    def test_detects_host(self, tmp_path: Path, remote: str, expected: str):
        assert detect_forge(_git_repo(tmp_path, remote)) == expected

    def test_matches_the_host_not_the_path(self, tmp_path: Path):
        # A repo *named* github-actions-demo is not hosted on GitHub. Matching
        # the whole URL would call this one wrong.
        repo = _git_repo(tmp_path, "git@git.acme.com:team/github-actions-demo.git")
        assert detect_forge(repo) == FORGE_UNKNOWN

    def test_falls_back_to_the_first_remote_when_origin_is_absent(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@gitlab.com:group/repo.git", name="upstream")
        assert detect_forge(repo) == FORGE_GITLAB

    def test_no_remote_and_no_repo_are_unknown_not_errors(self, tmp_path: Path):
        assert detect_forge(_git_repo(tmp_path / "bare")) == FORGE_UNKNOWN
        assert detect_forge(tmp_path / "not-a-repo") == FORGE_UNKNOWN


class TestBlock:
    def test_every_forge_has_a_distinct_block(self):
        blocks = {f: forge_block(f) for f in FORGES}
        assert len(set(blocks.values())) == len(FORGES)
        for forge, block in blocks.items():
            assert block.startswith("### Forge commands"), forge

    def test_blocks_carry_their_own_vocabulary(self):
        assert "gh pr edit" in forge_block(FORGE_GITHUB)
        assert "glab mr update" in forge_block(FORGE_GITLAB)
        assert "discussions rather than pull requests" in forge_block(FORGE_GITLAB)
        assert "no first-party CLI" in forge_block(FORGE_BITBUCKET)

    def test_details_checked_against_primary_docs(self):
        """Pin the details that were wrong in the first draft, so they can't drift back."""
        assert "/replies" in forge_block(FORGE_GITHUB)
        assert "-F resolved=true" in forge_block(FORGE_GITLAB)
        assert "notes/<note-id>" in forge_block(FORGE_GITLAB)
        assert "acli jira workitem view" in forge_block(FORGE_BITBUCKET)
        assert "quietly ignores fields" in forge_block(FORGE_BITBUCKET)
        # Shapes taken from the published OpenAPI spec, confirmed on a live repo.
        bitbucket = forge_block(FORGE_BITBUCKET)
        assert '"parent": {"id": <comment-id>}' in bitbucket
        assert "/resolve" in bitbucket
        assert '"destination": {"branch": {"name": "<branch>"}}' in bitbucket
        assert "Only open pull requests can be mutated" in bitbucket
        # Verified by introspecting the live GraphQL schema: threadId is the
        # only required input, and it comes from reviewThreads, not the comment.
        assert "resolveReviewThread(input: {threadId: $id})" in forge_block(FORGE_GITHUB)
        assert "reviewThreads(first: 100, after: $endCursor)" in forge_block(FORGE_GITHUB)

    def test_comment_reads_fetch_every_page(self):
        # Unpaged, GitHub returns 30 comments, GitLab 20, Bitbucket 10, with no error.
        github = forge_block(FORGE_GITHUB)
        for endpoint in ("pulls/<n>/comments", "pulls/<n>/reviews", "issues/<n>/comments"):
            assert f"gh api --paginate repos/{{owner}}/{{repo}}/{endpoint}" in github, endpoint
        # gh's GraphQL pagination needs both of these in the query.
        assert "query($endCursor: String)" in github
        assert "pageInfo { hasNextPage endCursor }" in github
        assert "glab api --paginate projects/:id/merge_requests/<iid>/discussions" in (
            forge_block(FORGE_GITLAB)
        )
        assert "follow each response's `next` URL" in forge_block(FORGE_BITBUCKET)

    def test_github_reads_conversation_comments(self):
        # PR conversation comments are issue comments on GitHub, not review comments.
        github = forge_block(FORGE_GITHUB)
        assert "issues/<n>/comments" in github
        assert "gh pr comment <n>" in github

    def test_github_placeholders_survive_as_single_braces(self):
        # gh fills repos/{owner}/{repo} itself; doubling them would break the call.
        assert "repos/{owner}/{repo}/pulls" in forge_block(FORGE_GITHUB)

    def test_unknown_block_asks_rather_than_guesses(self):
        block = forge_block(FORGE_UNKNOWN)
        assert "Never invent a command" in block
        assert "Ask the user which provider" in block

    def test_unrecognized_name_degrades_to_unknown(self):
        assert forge_block("perforce") == forge_block(FORGE_UNKNOWN)


class TestPermissions:
    """The adapter tells the agent to run a CLI; the allow-list has to match."""

    def test_cli_per_forge(self):
        assert forge_cli(FORGE_GITHUB) == "gh"
        assert forge_cli(FORGE_GITLAB) == "glab"
        # No first-party CLI exists for these, so allow-listing one would be noise.
        assert forge_cli(FORGE_BITBUCKET) is None
        assert forge_cli(FORGE_UNKNOWN) is None

    def test_detect_cli_from_the_repo(self, tmp_path: Path):
        assert detect_forge_cli(_git_repo(tmp_path, "git@gitlab.com:g/r.git")) == "glab"
        assert detect_forge_cli(tmp_path / "nope") is None

    def test_claude_settings_allow_the_detected_cli(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@github.com:owner/repo.git")
        generate_settings(repo=repo)
        allow = json.loads((repo / ".claude" / "settings.json").read_text())["permissions"]["allow"]
        assert "Bash(gh *)" in allow
        assert "Bash(glab *)" not in allow

    def test_no_cli_rule_when_the_host_has_none(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@bitbucket.org:ws/repo.git")
        generate_settings(repo=repo)
        allow = json.loads((repo / ".claude" / "settings.json").read_text())["permissions"]["allow"]
        assert not [rule for rule in allow if "gh *" in rule or "glab *" in rule]

    def test_other_agents_get_the_prefix_too(self):
        stack = dict.fromkeys(["python", "node", "go", "rust", "make"], False)
        assert "glab" in _shell_prefixes(stack, "glab")
        assert "gh" not in _shell_prefixes(stack, "glab")
        assert _shell_prefixes(stack) == ["git"]

    def test_stack_rules_are_untouched(self):
        stack = {"python": True, "node": False, "go": False, "rust": False, "make": False}
        assert "Bash(pytest *)" in _build_allowed_tools(stack, "gh")


class TestSubstitution:
    def test_claude_path_substitutes_the_detected_forge(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@gitlab.com:group/repo.git")
        (repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
        scaffold_skills(repo=repo)
        namespace = sanitize_skill_namespace(repo.name)
        for skill in FORGE_SKILLS:
            text = (repo / ".claude" / "skills" / f"{namespace}-{skill}" / "SKILL.md").read_text()
            assert "{{FORGE}}" not in text, f"{skill} left a literal token"
            assert "glab mr update" in text, f"{skill} missing the GitLab adapter"
            assert "gh pr edit" not in text, f"{skill} leaked GitHub commands"

    def test_payload_path_substitutes_and_honors_an_override(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@github.com:owner/repo.git")
        payloads = {p.skill: p for p in build_skill_payloads(repo=repo)}
        assert "gh pr edit" in payloads["restack"].body

        overridden = {p.skill: p for p in build_skill_payloads(repo=repo, forge=FORGE_BITBUCKET)}
        assert "api.bitbucket.org" in overridden["restack"].body

    def test_no_skill_leaks_a_literal_token(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@github.com:owner/repo.git")
        for payload in build_skill_payloads(repo=repo):
            assert "{{FORGE}}" not in payload.body, payload.skill
            for name, content in payload.aux_files.items():
                assert "{{FORGE}}" not in content, f"{payload.skill}/{name}"

    def test_each_skill_carries_only_the_sections_it_uses(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@github.com:owner/repo.git")
        payloads = {p.skill: p for p in build_skill_payloads(repo=repo)}
        assert "resolveReviewThread" in payloads["address-review"].body
        # The owl delegates feedback to address-review, so it carries core only.
        assert "resolveReviewThread" not in payloads["rest-of-the-owl"].body
        assert "gh pr create" in payloads["rest-of-the-owl"].body
        for skill in ("address-review", "rest-of-the-owl"):
            assert "gh stack" not in payloads[skill].body, skill
        for skill in ("restack", "split-pr"):
            assert "gh stack submit" in payloads[skill].body, skill
            assert "resolveReviewThread" not in payloads[skill].body, skill
        for payload in payloads.values():
            assert "<!-- forge:" not in payload.body, payload.skill
            assert "{{FORGE" not in payload.body, payload.skill

    @pytest.mark.parametrize("forge", FORGES)
    def test_every_forge_has_a_core_section(self, forge: str):
        sections = forge_sections(forge)
        assert sections["core"], forge
        # The full block is every section, so nothing is lost by the split.
        assert all(s in forge_block(forge) for s in sections.values())

    def test_skills_without_the_block_stay_lean(self, tmp_path: Path):
        repo = _git_repo(tmp_path, "git@github.com:owner/repo.git")
        payloads = {p.skill: p for p in build_skill_payloads(repo=repo)}
        assert "### Forge commands" not in payloads["debug"].body
        assert "### Forge commands" not in payloads["commit"].body
