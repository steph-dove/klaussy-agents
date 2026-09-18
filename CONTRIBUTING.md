# Contributing to klaussy

Thanks for your interest in improving klaussy! It's a Python CLI that scaffolds
conventions, skills, and hooks into repos for Claude Code, Gemini, Cursor,
Codex, Copilot, Antigravity, Cline, and Aider.

## Getting started

```bash
git clone https://github.com/steph-dove/klaussy-agents.git
cd klaussy-agents
uv sync --extra dev          # or: pip install -e ".[dev]"
uv run klaussy --help        # smoke-test the CLI
```

## Before you open a PR

Run the same checks CI runs:

```bash
uv run --extra dev ruff check src/ tests/      # lint
uv run --extra dev python -m pytest -q         # tests
```

Both must pass. New behavior needs test coverage — add cases for the happy path
and the error/edge paths.

## Guidelines

- **Keep PRs small and focused** — one concern per PR; say what changed and why.
- **Match the surrounding code** — naming, structure, and the existing module
  layout (`src/klaussy/...`). Comments explain *why*, not *what*.
- **Templates are the source of truth.** Skills, hooks, and conventions live in
  `src/klaussy/templates/`; both the `.claude` scaffold and the multi-agent
  fan-out read from them. Register a new skill/hook once and let the existing
  machinery emit it for every agent.
- **No secrets, ever.** A `gitleaks` scan runs in CI; keep credentials out of
  the tree.
- **The version lives in three files.** `pyproject.toml`,
  `src/klaussy/__init__.py`, *and* `.claude-plugin/plugin.json`. Claude Code
  pins an installed plugin to the manifest's `version` string, so a release
  that bumps the first two and forgets the third ships an update no existing
  plugin user receives. `tests/test_plugin_manifest.py` fails when they
  disagree. Don't add a `version` to the marketplace entry too — `plugin.json`
  silently wins over it.
- **The package is `klaussy-agents`.** `klaussy` and `klaussy-mcp` are console
  scripts, not distributions; neither exists on PyPI, so any
  `pip install klaussy` or `pipx run klaussy-mcp` in docs, skills, or manifests
  resolves to a 404. The MCP server also needs the optional extra —
  `klaussy-agents[mcp]`.
- **Skill templates end in `.tmpl`; only the repo-root `skills/` is real.**
  `gh skill install` and the Agent Skills spec discover skills by matching
  `skills/*/SKILL.md` *anywhere* in the tree, with no way to opt a directory
  out. Under the old `templates/skills/SKILL.md` layout, gh listed all 28
  templates as installable and then failed on every one, since
  `name: {{REPO}}-review` is not valid YAML (`{` opens a flow mapping). So a
  new template file is `SKILL.md.tmpl` under
  `src/klaussy/templates/skill-templates/` — the directory name documents the
  intent, the suffix is what enforces it. `TEMPLATE_SUFFIX` is stripped on the
  way out, so scaffolded repos still get plain `SKILL.md`.
  `tests/test_skill_discovery.py` enforces both halves.
- **The emitted filenames are a contract.** klaussy-desktop reads
  `.claude/skills/<repo>-precommit/SKILL.md`, its sibling `comment-cleanup.md`,
  and `<repo>-review/SKILL.md` by those exact names
  (`main/state/precommit-review.js`, `main/state/review-prompts.js`). Rename a
  template freely; never change what `template_output_name()` produces.

## Releasing

Bump all three version files together, update `CHANGELOG.md`, then tag `vX.Y.Z`
— `.github/workflows/release.yml` publishes to PyPI on the tag push.

Regenerating `examples/` needs `git add -f`: this repo's `.gitignore` ignores
`.claude/`, `.cursor/`, `CLAUDE.md` and friends, and those patterns are
unanchored, so they apply under `examples/` too. A plain `git add` looks like
it worked while silently dropping every new file.
- File bugs and feature requests as
  [issues](https://github.com/steph-dove/klaussy-agents/issues).

## Contributor Agreement

By submitting a contribution to this project, you agree that:

1. Your contribution is your original work.
2. You grant Dovatech LLC a perpetual, worldwide, non-exclusive, royalty-free
   license to use, modify, and distribute your contribution.
3. Your contribution is accepted under the terms of this project's license
   (MIT — see [`LICENSE`](LICENSE)).

Thanks for helping make klaussy better.
