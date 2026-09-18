# examples/

Real `klaussy init` output, captured by running the generator against two
well-known open-source Python projects. These are the **generated artifacts
only** — the upstream source is not vendored here.

| Example | Upstream repo | Upstream commit | Generated with |
|---|---|---|---|
| [`fastapi/`](fastapi/) | [fastapi/fastapi](https://github.com/fastapi/fastapi) | `50113da16` | klaussy 0.30.4 |
| [`httpx/`](httpx/) | [encode/httpx](https://github.com/encode/httpx) | `b5addb6` | klaussy 0.30.4 |

Both were generated with enrichment on (no `--skip-enrich`), which is what fills
the Decision Log and Known Pitfalls sections with prose read off the real source.
Regenerating without it produces a visibly thinner `CLAUDE.md`.

## What's in each

Everything `klaussy init` writes for all supported agents:

- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CONVENTIONS.md` — per-agent
  conventions, plus path-scoped `AGENTS.md`/`GEMINI.md` inside source
  subdirectories and `.github/instructions/` for Copilot.
- `.claude/`, `.cursor/`, `.codex/`, `.gemini/`, `.clinerules/`, `.agents/`,
  `.opencode/`, `.github/` — repo-namespaced skills (`fastapi-*`, `httpx-*`),
  hooks, and settings for each backend.
- Secret-exclusion files (`.cursorignore`, `.geminiignore`, …) and the
  per-agent commit/comment/read guards.

## Reproduce

```bash
git clone https://github.com/fastapi/fastapi
klaussy init --repo fastapi --base-branch master --all
```

Clone with full history — the discovery step reads git log for the decision log
and change hotspots, so a `--depth 1` clone produces a thinner CLAUDE.md.

`klaussy init` also appends a few entries to the target repo's `.gitignore`
(`pr-description.md`, `REVIEW_OUTPUT.md`, `plan.md`); that diff isn't reproduced
here since these directories hold only the newly generated files.

Copying the output back here needs `git add -f`: this repo's own `.gitignore`
ignores `.claude/`, `.cursor/`, `.codex/` and friends, and that applies just as
much under `examples/`. Files already committed stay tracked, so a plain
`git add` looks like it worked while silently dropping every *new* file — which
is how a fresh skill can land for some agents and not others.
