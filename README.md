# klaussy

[![PyPI version](https://img.shields.io/pypi/v/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![Python versions](https://img.shields.io/pypi/pyversions/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Multi-agent repo boilerplate generator. One command to make any repo ready for
**Claude Code, Gemini CLI, Cursor, Codex, GitHub Copilot, and Google Antigravity** — each gets the
same conventions and the same workflow skills in its own native format.

## Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [What Gets Generated](#what-gets-generated)
- [Multi-agent targets](#multi-agent-targets)
- [Options](#options)
- [Individual Commands](#individual-commands)
- [How It Works](#how-it-works)
- [Running klaussy](#running-klaussy)
- [Requirements](#requirements)

## Install

```bash
pip install klaussy-agents
```

Requires [klaussy-repo-conventions](https://pypi.org/project/klaussy-repo-conventions/) (installed automatically).

## Quick Start

```bash
cd your-repo
klaussy init
```

That's it. You'll be prompted for your base branch (auto-detects `dev`, `main`, etc.), then klaussy generates everything.

By default klaussy bootstraps **all** supported agents from the same conventions. To narrow to a subset, pass `--agents`:

```bash
klaussy init                                   # all agents (default)
klaussy init --agents claude                   # Claude Code only
klaussy init --agents claude,gemini,cursor     # a subset
```

See [Multi-agent targets](#multi-agent-targets) for what each agent gets.

## What Gets Generated

klaussy discovers your repo's conventions once, then writes — **for every selected agent (all six by default)** — that agent's native conventions file, the workflow skills, stack-appropriate permissions, and hooks where the agent supports them. Narrow with `--agents` to emit only the agents you want.

```
# Per agent (each gets the workflow skills + a conventions file + permissions + hooks):

Claude Code   CLAUDE.md  .claude/rules/  .claude/skills/<repo>-<skill>/  .claude/settings.json  .claude/hooks/
Gemini CLI    GEMINI.md  .gemini/skills/<repo>-<skill>/  .gemini/settings.json  .gemini/hooks/  .geminiignore
Cursor        .cursor/rules/*.mdc  .cursor/skills/<repo>-<skill>/  .cursor/permissions.json  .cursor/hooks.json  .cursorignore
Codex         AGENTS.md  .agents/skills/<repo>-<skill>/  .codex/config.toml  .codex/hooks.json
Copilot       .github/copilot-instructions.md  .github/instructions/  .github/skills/<repo>-<skill>/  .github/hooks/
Antigravity   AGENTS.md  .gemini/antigravity-cli/plugins/klaussy/{skills,rules}/  .gemini/antigravity-cli/plugins/klaussy/hooks.json  .agents/settings.json

# Every skills/ directory holds the same namespaced set:
#   <repo>-{review, precommit, plan, debug, implement, refactor, test, fix, pr, commit, explain, humanize, new-worktree}

# Shared, once:
.github/PULL_REQUEST_TEMPLATE.md   # only if the repo doesn't already have one
.gitignore                         # appends klaussy output exclusions (pr-description.md, REVIEW_OUTPUT.md, plan.md)
```

**What each piece does** — pre-commit and humanize first, since that's what most people reach for:

- **Pre-commit guard** — a `git commit` hook that runs your format + lint on the files being committed (plus a commented-out-code check on Python) and blocks the commit on failure. Wired into every agent.
- **Humanize** — strips AI tells (em-dashes, filler openers, chatbot scaffolding) from prose. The `<repo>-humanize` skill rewrites by spec; the deterministic `klaussy humanize` scrubber is a code-preserving backstop shared with klaussy-desktop.
- **Comment guard** — a hook that catches the agent's outgoing `gh` comment and humanizes it through that same scrubber before it posts. Wired into every agent.
- **Skills** — namespaced `<repo>-<skill>` workflow skills, auto-triggered by description, written into each agent's skills directory (detailed below).
- **CLAUDE.md** — auto-detected conventions, architecture, commands, and pitfalls; path-scoped rules split into `.claude/rules/*.md` and emitted in each agent's native file.
- **settings.json** — stack-detected tool permissions, plus deny rules that keep secrets (`.env`, `*.pem`, `credentials*`) out of the agent's reach.
- **Read-injection guard** — scans file reads and web fetches for prompt-injection markers before the agent consumes them.
- **PR template & .gitignore** — a PR template if your repo lacks one, and `.gitignore` entries for generated outputs.

### Comment guard

Before the agent posts a comment via `gh` (`gh pr comment`, `gh issue comment`, `gh pr review`), this hook runs the comment body through klaussy's deterministic humanize scrubber, so what actually lands has no AI tells.

On **Claude** it's transparent: a `PreToolUse` hook rewrites the command in place (via `updatedInput`) with the cleaned body, so the comment posts humanized with no extra round trip. On the **other agents** — whose hook protocols can't rewrite tool input — it blocks the post (`exit 2`) and hands back the humanized command for the agent to re-issue. Either way, the posted comment is scrubbed.

It only touches literal bodies (`-b` / `--body` / `--body=`); a shell-expanded body (`$(…)`) or one that's already clean passes through untouched, and a missing `klaussy` on `PATH` never blocks a post. The scrubbing is the same canonical implementation as the `<repo>-humanize` skill and the `klaussy humanize` CLI. Lives at `.claude/hooks/comment_guard.py` (and each agent's `klaussy_comment_guard.py`).

<details>
<summary><b>Example: what a generated skill looks like</b></summary>

Every skill is namespaced to your repo, carries an auto-trigger `description`, and gets a scoped tool allow-list. For a repo named `klaussy-agents`, `<repo>-fix` is written as `.claude/skills/klaussy-agents-fix/SKILL.md`:

```markdown
---
name: klaussy-agents-fix
description: Use when the user wants lint, format, and type errors fixed in the
  current changes. Reads CLAUDE.md for the repo's lint/format/type-check
  commands, runs each, and fixes only style/format/type issues.
allowed-tools: Read Grep Glob Bash Edit
---

Fix all lint, format, and type errors in the current changes.
...
```

The same skill is re-emitted in each target agent's native directory and syntax (see below).

</details>

See [Multi-agent targets](#multi-agent-targets) for the exact per-agent mapping (conventions, skill adaptation, secret exclusion, hook coverage), and the table below for what each skill does.

### The bundled skills

| Skill | What it does | Output |
|-------|-------------|--------|
| `<repo>-review` | Senior-level PR review against your base branch. Small PRs get a single-pass review; larger PRs fan out to parallel sub-agents (correctness, architecture, security, scope, plus an Agentic & Evals lens when the diff touches AI/agent/eval code, and an **Architecture Decision & Design-Doc lens when the PR contains an ADR/RFC/design doc**). Precision-biased (empty review is a valid outcome), every finding must name a concrete trigger, and a validation phase self-refutes and removes false positives. Comments default to a collaborative tone (say `blunt` for a terse review) and are humanized (no AI tells), keeping full detail either way | `REVIEW_OUTPUT.md` |
| `<repo>-precommit` | Last-mile review of a staged / about-to-commit diff across five lenses — silent failures, leaked secrets, debug leftovers, blatant correctness landmines, and excessive/narrating comments. Reports findings on the changed lines only; never refactors. Also the canonical source for klaussy-desktop's pre-commit gate (it's user-invoked, not auto-triggered) | — |
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
| `<repo>-humanize` | Strips AI tells from prose (files or pasted text): rewrites by the humanization spec, then runs the deterministic `klaussy humanize` scrubber as a guaranteed backstop. Never touches code | — |

### Migrating from 0.1.x

If you ran an earlier version of klaussy, you have `.claude/commands/*.md` files. On the next `klaussy init` (with 0.2.0+) those files — and only the ones klaussy itself created (tracked via `.claude/commands/.klaussy-version`) — are removed and replaced with `.claude/skills/<repo>-<skill>/SKILL.md`. Any commands you wrote yourself are left alone.

If you've already klaussified at 0.2.0+ and want to refresh after upgrading klaussy itself, use `klaussy init --force` (or the `klaussy-update` skill if you have the plugin installed).

## Multi-agent targets

klaussy discovers your repo's conventions **once** (into `CLAUDE.md` via klaussy-repo-conventions), then translates that plus the bundled workflow skills into each agent's native format. All six agents now read the open [Agent Skills](https://agentskills.io/specification) `SKILL.md` spec, so the skills are portable; klaussy places them in each agent's dedicated directory and adapts the bodies to that agent's capabilities.

| Agent | Conventions file | Skills directory | Permissions |
|-------|------------------|------------------|-------------|
| `claude` | `CLAUDE.md` + `.claude/rules/*.md` | `.claude/skills/<repo>-<skill>/` | `.claude/settings.json` (+ hooks) |
| `gemini` | `GEMINI.md` | `.gemini/skills/<repo>-<skill>/` | `.gemini/settings.json` |
| `cursor` | `.cursor/rules/*.mdc` | `.cursor/skills/<repo>-<skill>/` | `.cursor/permissions.json` |
| `codex` | `AGENTS.md` | `.agents/skills/<repo>-<skill>/` | `.codex/config.toml` |
| `copilot` | `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | `.github/skills/<repo>-<skill>/` | — (no committed allow-list; CLI gates via flags) |
| `antigravity` | `AGENTS.md` + plugin `rules/*.md` (`trigger: glob`) | `.gemini/antigravity-cli/plugins/klaussy/skills/<repo>-<skill>/` | `.agents/settings.json` (best-effort) + plugin `hooks.json` |

<details>
<summary><b>How skills are adapted per agent</b></summary>

The bundled skills are authored in Claude Code's syntax — `​```!` dynamic-shell blocks, parallel sub-agents via the `Agent`/`subagent_type` tool, and `ExitPlanMode`. klaussy rewrites the bodies to capture the same intent for each target: dynamic blocks become explicit "run this command" instructions, and skills that orchestrate sub-agents or plan mode get a short adaptation note. That note does **not** assume the other agents are single-threaded — as of 2026 Cursor (`Task`), Codex (`spawn_agent`), Gemini (subagents) and Copilot (`task`) all have a model-invocable parallel sub-agent tool, so the note tells the agent to map Claude's wording to its own equivalent (falling back to sequential only if it has none) and to use its own plan/approval mode. Simple skills (`commit`, `pr`, `explain`, …) reference none of this and are unchanged apart from path references.

</details>

<details>
<summary><b>How path-scoped rules map per agent</b></summary>

Path-scoped rules (`.claude/rules/*.md` with `paths:` frontmatter) map to each agent's own scoping mechanism: Cursor `globs:`, Copilot `applyTo:`, and Antigravity plugin rules `trigger: glob` + `globs:`. Gemini and Codex scope by *directory placement*, so a rule whose glob resolves to an existing subdirectory is emitted as a nested `GEMINI.md` / `AGENTS.md` in that directory (loaded only when that subtree is touched); rules whose globs don't map to a real directory fall back to inlined `### Applies to:` sections in the root file.

</details>

**Permissions & secrets.** Each agent gets a stack-appropriate command allow-list in its native format (`.claude/settings.json`, `.gemini/settings.json` `tools.allowed`, `.cursor/permissions.json` `terminalAllowlist`, `.codex/config.toml` approval/sandbox). For keeping secrets (`.env`, `*.pem`, `credentials*`, …) out of the agent's reach, klaussy uses each agent's native exclusion mechanism:

| Agent | Secret exclusion |
|-------|------------------|
| Claude | `deny` rules in `.claude/settings.json` |
| Gemini | `.geminiignore` (+ `respectGeminiIgnore` enabled in settings) — filters auto-discovery only; an explicit `@.env` still loads |
| Cursor | `.cursorignore` (the read-blocking one, not `.cursorindexingignore`) |
| Codex | **none possible** — Codex has no read-exclusion; `sandbox_mode` governs writes/network, not reads. Keep secrets outside the workspace. |
| Copilot | **not a committed file** — content exclusion is GitHub repo/org settings only, and doesn't cover the CLI/coding agent. |

Note: even where supported, ignore-file exclusion is best-effort. On Gemini it only filters automatic context discovery (an explicit `@.env` is still read); on Cursor the terminal and MCP tools bypass `.cursorignore` entirely. Neither stops a *terminal* tool from `cat`-ing a secret — pair it with the command allow-list (and the read/shell guards) for real protection.

**Hooks.** klaussy ships three guards — a **git-commit guard** (runs format + lint before a commit), a **comment guard** (humanizes an outgoing `gh` comment), and a **read-injection guard** (scans file/fetch content for prompt-injection markers). The guard scripts are cross-agent and dialect-tolerant: they extract the command/path from any agent's hook payload and block via `exit 2` + stderr, which every supported agent honors. klaussy wires each guard to whatever events the agent's protocol exposes:

| Guard | Claude | Gemini | Cursor | Codex | Copilot | Antigravity |
|-------|--------|--------|--------|-------|---------|-------------|
| git-commit | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| comment-humanize | ✅ rewrite | ✅ block | ✅ block | ✅ block | ✅ block | ✅ block |
| read-injection (local read) | ✅ | ✅ | ✅ | — | — | ✅ |
| read-injection (web fetch) | ✅ | ✅ | — | — | — | ✅ |

Codex exposes no pre-file-read hook event (only shell/tool execution), and Copilot's `preToolUse` is *fail-closed* (a crashing hook denies every tool call) with unconfirmed read-tool argument shapes — so for those two klaussy wires only the commit guard, and the guards are hardened to never crash (any parse error → allow). Config lands in each agent's native location: `.gemini/settings.json`, `.cursor/hooks.json`, `.codex/hooks.json`, `.github/hooks/klaussy-guards.json`, `.gemini/antigravity-cli/plugins/klaussy/hooks.json`.

<details>
<summary><b>Cross-platform hook details</b></summary>

The guard scripts are pure-stdlib Python with a `#!/usr/bin/env python3` shebang. Copilot uses its native `bash`/`powershell` hook split, so it runs the right interpreter on any OS. Cursor execs the script directly via its shebang. Gemini and Codex run a shell-string command, so klaussy writes the interpreter for the OS it runs on (`python3` on macOS/Linux, `python` on Windows); a mixed-OS team should ensure that interpreter resolves on each machine (Windows users: the python.org launcher honors the shebang).

</details>

<details>
<summary><b>Codex & Antigravity caveats</b></summary>

Codex's slash-prompt format is deprecated in favor of Skills, so klaussy emits Codex *Skills* (at `.agents/skills/`). Google Antigravity gets project-wide conventions via the cross-tool `AGENTS.md`, plus a committed Claude-style CLI plugin at `.gemini/antigravity-cli/plugins/klaussy/` (`plugin.json` marker, `hooks.json` guards, `skills/`, `rules/`). The Antigravity CLI loads plugins from `~/.gemini/antigravity-cli/plugins/`, so import or symlink the committed plugin there. The `hooks.json` uses Claude-style **events** (`PreToolUse`/`PostToolUse`) but Antigravity-native **tool matchers** (`run_command`, `view_file`, `read_url_content` — not Claude's `Bash`/`Read`/`WebFetch`), grouped under the plugin name. One thing still unverified against the (JS-rendered) official spec: whether the shared guard scripts **block** correctly under Antigravity's hook I/O (it reads `toolCall.args.*` and may expect a JSON `{"decision":"deny"}` on stdout rather than the `exit 2` other agents honor). The `.agents/settings.json` allow-list is best-effort.

</details>

## Options

```bash
klaussy init [OPTIONS]

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
klaussy init --review-template path/to/your-review.md
```

The template will be used as the body of the `<repo>-review` skill instead of the default. Custom templates are responsible for supplying their own SKILL.md frontmatter.

## Individual Commands

You can run each step individually:

```bash
klaussy checklist              # Regenerate the review skill from CLAUDE.md
klaussy skills                 # Regenerate all skills
klaussy settings               # Regenerate settings.json
klaussy hooks                  # Regenerate hook configs
klaussy github                 # Regenerate PR template
klaussy humanize [FILE...]     # Deterministically scrub AI tells from prose (stdin if no files)
```

All subcommands support `--repo`, `--force`, and `--base-branch` where applicable. `skills`, `settings`, and `init` also accept `--agents`/`--all` to target agents beyond Claude.

## How It Works

1. Runs `conventions discover --claude --init` to analyze your codebase and generate `CLAUDE.md` with path-scoped conventions and architecture sections
2. Parses `CLAUDE.md` to extract conventions, commands, and pitfalls (including which file globs each rule applies to)
3. Injects those into the review skill template so `<repo>-review` checks repo-specific rules with the right path scope
4. Detects your stack from marker files (`pyproject.toml`, `package.json`, `go.mod`, etc.)
5. Sets permissions, deny rules, and hooks based on what it finds
6. Skips anything that already exists (PR template) unless `--force` is used
7. Translates the conventions and skills into each selected agent's native files — by default, all six (see [Multi-agent targets](#multi-agent-targets))

## Running klaussy

The CLI is agent-agnostic — `klaussy init` scaffolds whichever agents you target (all six by default). It's also usable as a Python library, and — if you use Claude Code — as a plugin or MCP server:

### As a CLI (simplest)

```bash
pip install klaussy-agents
klaussy init
```

### As a Claude Code Plugin

Add the klaussy marketplace, then install the plugin:

```
/plugin marketplace add steph-dove/klaussy-agents
/plugin install klaussy@klaussy
```

This gives you two plugin-level skills — `klaussy-init` (scaffold a fresh repo) and `klaussy-update` (refresh generated boilerplate after upgrading klaussy) — plus the MCP server. The plugin manifest lives in `.claude-plugin/plugin.json` and the marketplace entry in `.claude-plugin/marketplace.json`.

### As an MCP Server

Add klaussy as an MCP server so Claude can invoke it directly:

```bash
pip install klaussy-agents[mcp]
claude mcp add --transport stdio klaussy -- klaussy-mcp
```

Or add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "klaussy": {
      "command": "klaussy-mcp",
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

The MCP server exposes one tool per CLI command: `klaussy_init`, `klaussy_checklist`, `klaussy_skills`, `klaussy_settings`, `klaussy_hooks`, `klaussy_github`, `klaussy_humanize`, plus `klaussy_status`.

### As a Python library

Every operation the CLI runs is available programmatically from `klaussy.toolkit` — no subprocess, no prompts. Handy for scripting scaffolds across many repos or wiring klaussy into your own tooling.

```python
from klaussy import toolkit

# Scaffold selected agents; returns a ScaffoldResult.
result = toolkit.init(repo=".", agents=["claude", "gemini"])
print(result.completed, result.skipped, result.ok)

# Individual steps mirror the CLI commands.
toolkit.skills(repo=".", agents=["claude"])
toolkit.settings(repo=".")
toolkit.hooks(repo=".")
toolkit.github(repo=".")
toolkit.checklist(repo=".")

# Scrub AI tells from a string (or files).
clean = toolkit.humanize("A great solution — it works.")
toolkit.humanize_files(["NOTES.md"], write=True)

# Which klaussy files exist in a repo.
toolkit.status(repo=".")   # {"CLAUDE.md": "exists", ...}
```

`agents` accepts a list, a single key, or `"all"` (the default); an unset `base_branch` is auto-detected. Import from `klaussy.toolkit` — the internal modules may move between releases, but that namespace is the supported surface.

## Requirements

- Python 3.10+
- [klaussy-repo-conventions](https://pypi.org/project/klaussy-repo-conventions/) >= 1.4.0
- [Claude Code CLI](https://www.npmjs.com/package/@anthropic-ai/claude-code) (optional, for `--init` enrichment)
- [mcp](https://pypi.org/project/mcp/) (optional, for MCP server: `pip install klaussy-agents[mcp]`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.

## Ownership and Governance

klaussy is an open-source project owned and maintained by Dovatech LLC.

Dovatech LLC is a privately held company founded and wholly owned by Stephanie Dover, who is also the original author and lead maintainer of this project.
