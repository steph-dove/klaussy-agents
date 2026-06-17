# klausify

Multi-agent repo boilerplate generator. One command to make any repo ready for
**Claude Code, Gemini CLI, Cursor, Codex, and GitHub Copilot** — each gets the
same conventions and the same workflow skills in its own native format.

## Install

```bash
pip install klausify
```

Requires [conventions-cli](https://pypi.org/project/conventions-cli/) (installed automatically).

## Quick Start

```bash
cd your-repo
klausify init
```

That's it. You'll be prompted for your base branch (auto-detects `dev`, `main`, etc.), then klausify generates everything.

By default klausify bootstraps **all** supported agents from the same conventions. To narrow to a subset, pass `--agents`:

```bash
klausify init                                   # all agents (default)
klausify init --agents claude                   # Claude Code only
klausify init --agents claude,gemini,cursor     # a subset
```

See [Multi-agent targets](#multi-agent-targets) for what each agent gets.

## What Gets Generated

```
CLAUDE.md                                      # Repo conventions, project-wide section (via conventions-cli)

.claude/
├── settings.json                              # Tool permissions + deny rules + PreToolUse/PostToolUse hooks
├── hooks/
│   ├── read_injection_guard.py                # Scans Read/WebFetch content for prompt-injection markers
│   └── git_commit_guard.py                    # Runs format + lint when Claude tries to `git commit`
├── rules/
│   └── <glob-stem>.md                         # Path-scoped rule buckets (zero or more, emitted by conventions-cli 1.4+)
└── skills/
    ├── .klausify-version                      # Marker tracking which klausify version generated the skills
    ├── <repo>-review/SKILL.md                 # PR review with parallel sub-agents and repo-specific checks
    ├── <repo>-plan/SKILL.md                   # Multi-phase plan + implement (discovery, parallel architects, review)
    ├── <repo>-debug/SKILL.md                  # Debug an error with root-cause analysis and a failing test
    ├── <repo>-implement/SKILL.md              # Implement a pasted ticket/design with plan-mode investigation
    ├── <repo>-refactor/SKILL.md               # Refactor code while preserving behavior, test-backed
    ├── <repo>-test/SKILL.md                   # Write tests for current changes
    ├── <repo>-fix/SKILL.md                    # Fix lint/format/type errors
    ├── <repo>-pr/SKILL.md                     # Generate a PR description
    ├── <repo>-commit/SKILL.md                 # Generate a commit message
    ├── <repo>-explain/SKILL.md                # Explain code or current diff
    └── <repo>-new-worktree/SKILL.md           # Create a git worktree for a task

.github/
└── PULL_REQUEST_TEMPLATE.md                   # Only if repo doesn't have one

.gitignore                                     # Appends klausify output exclusions
```

### What each piece does

**CLAUDE.md** — Auto-detected conventions, architecture, commands, and pitfalls for your repo. As of 0.2.0 path-scoped rules are split out into individual files under `.claude/rules/<glob-stem>.md` (each with `paths:` frontmatter) so rules apply where they belong instead of as a flat list — `CLAUDE.md` itself holds the project-wide content. This is what Claude Code reads to understand your project.

**settings.json** — Auto-detects your stack (Python, Node, Go, Rust, Make) and sets tool permissions. Detects sensitive files (`.env`, `*.pem`, `credentials*`) and adds deny rules so Claude can't read them.

**Skills** — Each repo gets a set of namespaced skills (`<repo>-<skill>`) so Claude Code auto-triggers them by description and they don't collide across repos. The bundled set is listed below; the canonical list lives in `SKILL_NAMES` in `src/klausify/skills.py`.

| Skill | What it does | Output |
|-------|-------------|--------|
| `<repo>-review` | Senior-level PR review against your base branch. Small PRs get a single-pass review; larger PRs fan out to parallel sub-agents (correctness, architecture, security, scope, plus an Agentic & Evals lens when the diff touches AI/agent/eval code) with a validation phase that removes false positives | `REVIEW_OUTPUT.md` |
| `<repo>-plan` | Multi-phase task planning + implementation: discovery → parallel exploration → clarify → parallel architectures → approval → implement → parallel review → summary. The approved plan is written to `plan.md` and used as a resumable checklist | `plan.md` |
| `<repo>-test` | Writes tests for current changes matching your repo's test patterns. Covers happy path, edge cases, and error paths without over-mocking | — |
| `<repo>-fix` | Fixes all lint, format, and type errors | — |
| `<repo>-pr` | Generates a ready-to-paste PR description | `pr-description.md` |
| `<repo>-commit` | Generates a commit message from staged changes | — |
| `<repo>-debug` | Five-phase debug flow: reproduce, diagnose root cause, write a failing test, fix, verify against the full suite | — |
| `<repo>-implement` | Implements a pasted ticket or design doc. Uses plan mode to investigate and plan before editing, enforces scope rules, and writes failing tests first for bug fixes | — |
| `<repo>-refactor` | Refactors code while preserving behavior exactly. Requires a passing test baseline, runs tests between every incremental step | — |
| `<repo>-new-worktree` | Creates a git worktree with a branch named for your task | — |
| `<repo>-explain` | Explains code or concept; defaults to explaining the current diff | — |

**Git-commit guard** — A `PreToolUse` hook on `Bash` that watches for `git commit` invocations. When Claude is about to commit, the guard runs your auto-detected format + lint commands and blocks the commit on any non-zero exit. Project-specific commands are baked into `.claude/hooks/git_commit_guard.py` at scaffold time.

**Read-injection guard** — A `PreToolUse` hook (for `Read`) and `PostToolUse` hook (for `WebFetch`) that scans content for prompt-injection markers (`ignore previous instructions`, ChatML/Llama control tokens, role-prefix injection, persona reassignment) before Claude consumes it. Local files matching the patterns are blocked; web responses are surfaced back as untrusted-content warnings. Pure-stdlib Python so the repo stays portable. Lives at `.claude/hooks/read_injection_guard.py`.

**PR template** — A basic PR template, only created if your repo doesn't already have one (checks root, `.github/`, and `docs/`).

**.gitignore** — Appends `pr-description.md`, `REVIEW_OUTPUT.md`, and `plan.md` so generated outputs don't get committed.

### Migrating from 0.1.x

If you ran an earlier version of klausify, you have `.claude/commands/*.md` files. On the next `klausify init` (with 0.2.0+) those files — and only the ones klausify itself created (tracked via `.claude/commands/.klausify-version`) — are removed and replaced with `.claude/skills/<repo>-<skill>/SKILL.md`. Any commands you wrote yourself are left alone.

If you've already klausified at 0.2.0+ and want to refresh after upgrading klausify itself, use `klausify init --force` (or the `klausify-update` skill if you have the plugin installed).

## Multi-agent targets

klausify discovers your repo's conventions **once** (into `CLAUDE.md` via conventions-cli), then translates that plus the bundled workflow skills into each agent's native format. All five agents now read the open [Agent Skills](https://agentskills.io/specification) `SKILL.md` spec, so the skills are portable; klausify places them in each agent's dedicated directory and adapts the bodies to that agent's capabilities.

| Agent | Conventions file | Skills directory | Permissions |
|-------|------------------|------------------|-------------|
| `claude` | `CLAUDE.md` + `.claude/rules/*.md` | `.claude/skills/<repo>-<skill>/` | `.claude/settings.json` (+ hooks) |
| `gemini` | `GEMINI.md` | `.gemini/skills/<repo>-<skill>/` | `.gemini/settings.json` |
| `cursor` | `.cursor/rules/*.mdc` | `.cursor/skills/<repo>-<skill>/` | `.cursor/permissions.json` |
| `codex` | `AGENTS.md` | `.agents/skills/<repo>-<skill>/` | `.codex/config.toml` |
| `copilot` | `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | `.github/skills/<repo>-<skill>/` | — (no per-repo model) |

**Skill adaptation.** The bundled skills are authored for Claude Code, which has `​```!` dynamic-shell blocks, parallel sub-agents, and a plan mode. For agents that lack those, klausify rewrites the bodies to capture the same request: dynamic blocks become explicit "run this command" instructions, and skills that orchestrate sub-agents or plan mode get a short adaptation note telling the agent to do that work sequentially / to seek approval before editing. Simple skills (`commit`, `pr`, `explain`, …) are unchanged apart from path references.

**Conventions mapping.** Path-scoped rules (`.claude/rules/*.md` with `paths:` frontmatter) map to each agent's own scoping mechanism: Cursor `globs:`, Copilot `applyTo:`, and inlined `### Applies to:` sections for `GEMINI.md` / `AGENTS.md`.

**Hooks.** klausify ships two guards — a **git-commit guard** (runs format + lint before a commit) and a **read-injection guard** (scans file/fetch content for prompt-injection markers). The guard scripts are cross-agent and dialect-tolerant: they extract the command/path from any agent's hook payload and block via `exit 2` + stderr, which every supported agent honors. klausify wires each guard to whatever events the agent's protocol exposes:

| Guard | Claude | Gemini | Cursor | Codex | Copilot |
|-------|--------|--------|--------|-------|---------|
| git-commit | ✅ | ✅ | ✅ | ✅ | ✅ |
| read-injection (local read) | ✅ | ✅ | ✅ | — | — |
| read-injection (web fetch) | ✅ | ✅ | — | — | — |

Codex exposes no pre-file-read hook event (only shell/tool execution), and Copilot's `preToolUse` is *fail-closed* (a crashing hook denies every tool call) with unconfirmed read-tool argument shapes — so for those two klausify wires only the commit guard, and the guards are hardened to never crash (any parse error → allow). Config lands in each agent's native location: `.gemini/settings.json`, `.cursor/hooks.json`, `.codex/hooks.json`, `.github/hooks/klausify-guards.json`.

**Other caveats.** Codex's slash-prompt format is deprecated in favor of Skills, so klausify emits Codex *Skills* (at `.agents/skills/`). Copilot has no per-repo permission model, so its settings step is skipped.

## Options

```bash
klausify init [OPTIONS]

Options:
  -r, --repo PATH             Target repository (default: current directory)
  -f, --force                 Overwrite existing files
  -b, --base-branch TEXT      Base branch for diffs (default: auto-detect, prompts)
  --skip-enrich               Skip Claude CLI enrichment (faster, no API call)
  --review-template PATH      Use a custom review prompt instead of the default
  --agents TEXT               Comma list of target agents to narrow to (default: all)
  --all                       Scaffold every supported agent (the default)
```

### Custom review template

If your team has a specific review checklist (e.g. domain-specific checks, security requirements), pass it in:

```bash
klausify init --review-template path/to/your-review.md
```

The template will be used as the body of the `<repo>-review` skill instead of the default. Custom templates are responsible for supplying their own SKILL.md frontmatter.

## Individual Commands

You can run each step individually:

```bash
klausify checklist              # Regenerate the review skill from CLAUDE.md
klausify skills                 # Regenerate all skills
klausify settings               # Regenerate settings.json
klausify hooks                  # Regenerate hook configs
klausify github                 # Regenerate PR template
```

All subcommands support `--repo`, `--force`, and `--base-branch` where applicable. `skills`, `settings`, and `init` also accept `--agents`/`--all` to target agents beyond Claude.

## How It Works

1. Runs `conventions discover --claude --init` to analyze your codebase and generate `CLAUDE.md` with path-scoped conventions and architecture sections
2. Parses `CLAUDE.md` to extract conventions, commands, and pitfalls (including which file globs each rule applies to)
3. Injects those into the review skill template so `<repo>-review` checks repo-specific rules with the right path scope
4. Detects your stack from marker files (`pyproject.toml`, `package.json`, `go.mod`, etc.)
5. Sets permissions, deny rules, and hooks based on what it finds
6. Skips anything that already exists (PR template) unless `--force` is used

## Claude Code Integration

klausify can be used three ways with Claude Code:

### As a CLI (simplest)

```bash
pip install klausify
klausify init
```

### As a Claude Code Plugin

Add the klausify marketplace, then install the plugin:

```
/plugin marketplace add steph-dove/klausify
/plugin install klausify@klausify
```

This gives you two plugin-level skills — `klausify-init` (scaffold a fresh repo) and `klausify-update` (refresh generated boilerplate after upgrading klausify) — plus the MCP server. The plugin manifest lives in `.claude-plugin/plugin.json` and the marketplace entry in `.claude-plugin/marketplace.json`.

### As an MCP Server

Add klausify as an MCP server so Claude can invoke it directly:

```bash
pip install klausify[mcp]
claude mcp add --transport stdio klausify -- klausify-mcp
```

Or add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "klausify": {
      "command": "klausify-mcp",
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

The MCP server exposes these tools: `klausify_init`, `klausify_checklist`, `klausify_skills`, `klausify_settings`, `klausify_status`.

## Requirements

- Python 3.10+
- [conventions-cli](https://pypi.org/project/conventions-cli/) >= 1.4.0
- [Claude Code CLI](https://www.npmjs.com/package/@anthropic-ai/claude-code) (optional, for `--init` enrichment)
- [mcp](https://pypi.org/project/mcp/) (optional, for MCP server: `pip install klausify[mcp]`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.

## Ownership and Governance

klausify is an open-source project owned and maintained by Dovatech LLC.

Dovatech LLC is a privately held company founded and wholly owned by Stephanie Dover, who is also the original author and lead maintainer of this project.
