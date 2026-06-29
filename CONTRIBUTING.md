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
