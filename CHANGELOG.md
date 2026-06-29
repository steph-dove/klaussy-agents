# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Releases
before 0.6.0 are recorded in the git tags (`v0.2.0`–`v0.5.1`).

## [0.10.0]

### Added

- **Dependency gate hook** — a new cross-agent guard that blocks package-manager
  commands adding a *new named* dependency (`pip install requests`, `npm install
  lodash`, `poetry add`, `cargo add`, `go get`, …) so the agent confirms it's
  actually needed before bloating the manifest. Bare manifest syncs (`npm
  install`, `pip install -r requirements.txt`, `uv sync`) pass through untouched;
  prefix a confirmed install with `KLAUSSY_DEPS_OK=1` to proceed. Wired into all
  seven agents with a pre-shell hook (Claude, Gemini, Cursor, Codex, Copilot,
  Antigravity, Cline).
- **`adr-generator` skill** — drafts Architecture Decision Records, matching the
  repo's existing ADR location and template (MADR/Nygard) or establishing one.
- **`security-audit` skill** — a focused, diff-scoped security pass (secrets,
  injection, SSRF, access control, unsafe deserialization, new/vulnerable
  dependencies); narrower and deeper than the general `review` skill.
- **Shared session state** — `klaussy init` scaffolds `.agents/session.json`, a
  tool-neutral handoff note (branch, task, plan, known failures) any agent can
  read at session start and update as work progresses, so switching between tools
  doesn't mean re-discovering the active task. Live state is gitignored; the
  committed `.agents/SESSION.md` documents the contract.

### Fixed

- Capability banners are now detected against the *adapted* skill body, so a
  sub-agent / plan-mode mention inside a stripped dynamic-shell block no longer
  triggers a spurious banner.

## [0.9.0]

### Added

- **Aider (Ollama) backend** — model-agnostic, commonly run on a local Ollama
  model. Emits a flat `CONVENTIONS.md` (project-wide conventions + inlined
  path-scoped rules) wired into `.aider.conf.yml`'s `read:` key,
  `auto-lint`/`lint-cmd` + `test-cmd` gating, and `.aiderignore` read blocks.
  Aider has no skills/hooks mechanism, so those steps are skipped with an honest
  note.

## [0.8.0]

### Changed

- Commit guard is now scoped to the diff, and a verbose-comment check was added.

## [0.7.1]

### Changed

- `plan` skill: refreshed the Phase 5 approval template.

## [0.7.0]

### Added

- Full **Cline** backend support.

## [0.6.0]

### Added

- **Comment guard** — a new hook, wired into every agent, that humanizes the
  agent's outgoing `gh` comment (`gh pr comment` / `issue comment` / `pr
  review`) before it posts. On Claude it rewrites the command in place via the
  `PreToolUse` `updatedInput` field; on the other agents (which can't rewrite
  tool input) it blocks the post and returns the humanized command to re-issue.
- `klaussy.toolkit` — a public Python library surface for every scaffolding
  operation (`init`, `skills`, `settings`, `hooks`, `github`, `checklist`,
  `humanize`, `humanize_files`, `status`), plus the `ScaffoldResult` type. No
  subprocess and no interactive prompts: the base branch is auto-detected and
  `agents` accepts a list, a single key, or `"all"`.
- MCP tools `klaussy_hooks`, `klaussy_github`, and `klaussy_humanize`, giving the
  server one tool per CLI command (alongside `klaussy_status`).

### Changed

- The `fix` and `test` skills now scope to `BASE_BRANCH...HEAD` plus the working
  tree instead of running tools over the whole repo (or, for `test`, a bare
  `git diff` that missed committed branch work).

### Fixed

- The git-commit guard now runs format/lint **scoped to the files being
  committed** instead of the entire repository, so pre-existing issues in
  untouched files no longer block an unrelated commit. The Claude guard also
  allows the commit when a checker binary is missing, matching the cross-agent
  guard.
- The MCP server's `klaussy_status` reported skills from a stale `SKILL_NAMES`
  copy that omitted `precommit` and `humanize`; it now uses the canonical list
  via `klaussy.toolkit.status`.

### Documentation

- README: added the `precommit` skill, badges, a table of contents, a
  generated-skill example, and an "As a Python library" section; condensed the
  per-piece descriptions and led with pre-commit and humanize.
