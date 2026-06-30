# examples/

Real `klaussy init` output, captured by running the generator against two
well-known open-source Python projects. These are the **generated artifacts
only** — the upstream source is not vendored here.

| Example | Upstream repo | Generated with |
|---|---|---|
| [`fastapi/`](fastapi/) | [fastapi/fastapi](https://github.com/fastapi/fastapi) | klaussy 0.12.1 |
| [`httpx/`](httpx/) | [encode/httpx](https://github.com/encode/httpx) | klaussy 0.12.1 |

## What's in each

Everything `klaussy init` writes for all supported agents:

- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CONVENTIONS.md` — per-agent
  conventions, plus path-scoped `AGENTS.md`/`GEMINI.md` inside source
  subdirectories and `.github/instructions/` for Copilot.
- `.claude/`, `.cursor/`, `.codex/`, `.gemini/`, `.clinerules/`, `.agents/`,
  `.github/` — repo-namespaced skills (`fastapi-*`, `httpx-*`), hooks, and
  settings for each backend.
- Secret-exclusion files (`.cursorignore`, `.geminiignore`, …) and the
  per-agent commit/comment/read guards.

## Reproduce

```bash
git clone https://github.com/fastapi/fastapi
klaussy init --repo fastapi --base-branch master
```

`klaussy init` also appends a few entries to the target repo's `.gitignore`
(`pr-description.md`, `REVIEW_OUTPUT.md`, `plan.md`); that diff isn't reproduced
here since these directories hold only the newly generated files.
