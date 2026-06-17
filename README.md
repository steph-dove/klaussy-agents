# klaussy

Multi-agent repo boilerplate generator. One command to make any repo ready for
**Claude Code, Gemini CLI, Cursor, Codex, and GitHub Copilot** — each gets the
same conventions and the same workflow skills in its own native format.

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

klaussy discovers your repo's conventions once, then writes — **for every selected agent (all five by default)** — that agent's native conventions file, the workflow skills, stack-appropriate permissions, and hooks where the agent supports them. Narrow with `--agents` to emit only the agents you want.

```
# Per agent (each gets the workflow skills + a conventions file + permissions + hooks):

Claude Code   CLAUDE.md  .claude/rules/  .claude/skills/<repo>-<skill>/  .claude/settings.json  .claude/hooks/
Gemini CLI    GEMINI.md  .gemini/skills/<repo>-<skill>/  .gemini/settings.json  .gemini/hooks/  .geminiignore
Cursor        .cursor/rules/*.mdc  .cursor/skills/<repo>-<skill>/  .cursor/permissions.json  .cursor/hooks.json  .cursorignore
Codex         AGENTS.md  .agents/skills/<repo>-<skill>/  .codex/config.toml  .codex/hooks.json
Copilot       .github/copilot-instructions.md  .github/instructions/  .github/skills/<repo>-<skill>/  .github/hooks/

# Every skills/ directory holds the same namespaced set:
#   <repo>-{review, plan, debug, implement, refactor, test, fix, pr, commit, explain, new-worktree}

# Shared, once:
.github/PULL_REQUEST_TEMPLATE.md   # only if the repo doesn't already have one
.gitignore                         # appends klaussy output exclusions (pr-description.md, REVIEW_OUTPUT.md, plan.md)
```

See [Multi-agent targets](#multi-agent-targets) for the exact per-agent mapping (conventions, skill adaptation, secret exclusion, hook coverage), and the table below for what each skill does.

### What each piece does

**CLAUDE.md** — Auto-detected conventions, architecture, commands, and pitfalls for your repo. As of 0.2.0 path-scoped rules are split out into individual files under `.claude/rules/<glob-stem>.md` (each with `paths:` frontmatter) so rules apply where they belong instead of as a flat list — `CLAUDE.md` itself holds the project-wide content. It's the conventions source each agent reads, emitted in that agent's native file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.github/copilot-instructions.md`, or `.cursor/rules/`).

**settings.json** — Auto-detects your stack (Python, Node, Go, Rust, Make) and sets tool permissions. Detects sensitive files (`.env`, `*.pem`, `credentials*`) and adds deny rules so the agent can't read them. Each agent gets this in its native form — see **Permissions & secrets** under [Multi-agent targets](#multi-agent-targets).

**Skills** — Each repo gets a set of namespaced skills (`<repo>-<skill>`) so the agent auto-triggers them by description and they don't collide across repos. They're written into each selected agent's skills directory (`.claude/skills/`, `.gemini/skills/`, `.cursor/skills/`, `.agents/skills/`, `.github/skills/`). The bundled set is listed below; the canonical list lives in `SKILL_NAMES` in `src/klaussy/skills.py`. Prose-output skills (review, pr, commit, explain) share one humanization spec (`HUMANIZE_BLOCK`) so their output reads human — no em-dashes, filler openers, or chatbot scaffolding — across every agent. For a hard guarantee independent of how well the model complied, klaussy also ships a **deterministic, code-preserving scrubber**: the `klaussy.humanize` module and a `klaussy humanize` CLI (pipe a comment with `printf '%s' "$c" | klaussy humanize`, or scrub files with `klaussy humanize FILE --write` / `--check`). Both the prompt spec and the scrubber are faithful ports of klaussy-desktop's `humanize-comment.js`, so desktop and CI can pipe through this one canonical implementation instead of diverging.

| Skill | What it does | Output |
|-------|-------------|--------|
| `<repo>-review` | Senior-level PR review against your base branch. Small PRs get a single-pass review; larger PRs fan out to parallel sub-agents (correctness, architecture, security, scope, plus an Agentic & Evals lens when the diff touches AI/agent/eval code, and an **Architecture Decision & Design-Doc lens when the PR contains an ADR/RFC/design doc**). Precision-biased (empty review is a valid outcome), every finding must name a concrete trigger, and a validation phase self-refutes and removes false positives. Comments default to a collaborative tone (say `blunt` for a terse review) and are humanized (no AI tells), keeping full detail either way | `REVIEW_OUTPUT.md` |
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

**Git-commit guard** — A `PreToolUse` hook on `Bash` that watches for `git commit` invocations. When the agent is about to commit, the guard runs your auto-detected format + lint commands and blocks the commit on any non-zero exit. The same guard is wired into every selected agent (see **Hooks** under [Multi-agent targets](#multi-agent-targets)). For Python it also runs a deterministic commented-out-code check (`ruff check --select ERA`, block-only — it flags the lines, never deletes them). Project-specific commands are baked into `.claude/hooks/git_commit_guard.py` at scaffold time. The broader, judgment-based comment hygiene (verbose/narrating comments → condense or delete, keep only "why") can't be done deterministically, so it lives in the skills: the review skill flags it, and the implement/refactor/fix skills avoid writing it.

**Read-injection guard** — A `PreToolUse` hook (for `Read`) and `PostToolUse` hook (for `WebFetch`) that scans content for prompt-injection markers (`ignore previous instructions`, ChatML/Llama control tokens, role-prefix injection, persona reassignment) before the agent consumes it. Local files matching the patterns are blocked; web responses are surfaced back as untrusted-content warnings. Pure-stdlib Python so the repo stays portable. Lives at `.claude/hooks/read_injection_guard.py`.

**PR template** — A basic PR template, only created if your repo doesn't already have one (checks root, `.github/`, and `docs/`).

**.gitignore** — Appends `pr-description.md`, `REVIEW_OUTPUT.md`, and `plan.md` so generated outputs don't get committed.

### Migrating from 0.1.x

If you ran an earlier version of klaussy, you have `.claude/commands/*.md` files. On the next `klaussy init` (with 0.2.0+) those files — and only the ones klaussy itself created (tracked via `.claude/commands/.klaussy-version`) — are removed and replaced with `.claude/skills/<repo>-<skill>/SKILL.md`. Any commands you wrote yourself are left alone.

If you've already klaussified at 0.2.0+ and want to refresh after upgrading klaussy itself, use `klaussy init --force` (or the `klaussy-update` skill if you have the plugin installed).

## Multi-agent targets

klaussy discovers your repo's conventions **once** (into `CLAUDE.md` via klaussy-repo-conventions), then translates that plus the bundled workflow skills into each agent's native format. All five agents now read the open [Agent Skills](https://agentskills.io/specification) `SKILL.md` spec, so the skills are portable; klaussy places them in each agent's dedicated directory and adapts the bodies to that agent's capabilities.

| Agent | Conventions file | Skills directory | Permissions |
|-------|------------------|------------------|-------------|
| `claude` | `CLAUDE.md` + `.claude/rules/*.md` | `.claude/skills/<repo>-<skill>/` | `.claude/settings.json` (+ hooks) |
| `gemini` | `GEMINI.md` | `.gemini/skills/<repo>-<skill>/` | `.gemini/settings.json` |
| `cursor` | `.cursor/rules/*.mdc` | `.cursor/skills/<repo>-<skill>/` | `.cursor/permissions.json` |
| `codex` | `AGENTS.md` | `.agents/skills/<repo>-<skill>/` | `.codex/config.toml` |
| `copilot` | `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | `.github/skills/<repo>-<skill>/` | — (no per-repo model) |

**Skill adaptation.** The bundled skills are authored in Claude Code's syntax — `​```!` dynamic-shell blocks, parallel sub-agents via the `Agent`/`subagent_type` tool, and `ExitPlanMode`. klaussy rewrites the bodies to capture the same intent for each target: dynamic blocks become explicit "run this command" instructions, and skills that orchestrate sub-agents or plan mode get a short adaptation note. That note does **not** assume the other agents are single-threaded — as of 2026 Cursor (`Task`), Codex (`spawn_agent`), Gemini (subagents) and Copilot (`task`) all have a model-invocable parallel sub-agent tool, so the note tells the agent to map Claude's wording to its own equivalent (falling back to sequential only if it has none) and to use its own plan/approval mode. Simple skills (`commit`, `pr`, `explain`, …) reference none of this and are unchanged apart from path references.

**Conventions mapping.** Path-scoped rules (`.claude/rules/*.md` with `paths:` frontmatter) map to each agent's own scoping mechanism: Cursor `globs:`, Copilot `applyTo:`, and inlined `### Applies to:` sections for `GEMINI.md` / `AGENTS.md`.

**Permissions & secrets.** Each agent gets a stack-appropriate command allow-list in its native format (`.claude/settings.json`, `.gemini/settings.json` `tools.allowed`, `.cursor/permissions.json` `terminalAllowlist`, `.codex/config.toml` approval/sandbox). For keeping secrets (`.env`, `*.pem`, `credentials*`, …) out of the agent's reach, klaussy uses each agent's native exclusion mechanism:

| Agent | Secret exclusion |
|-------|------------------|
| Claude | `deny` rules in `.claude/settings.json` |
| Gemini | `.geminiignore` (+ `respectGeminiIgnore` enabled in settings) |
| Cursor | `.cursorignore` (the read-blocking one, not `.cursorindexingignore`) |
| Codex | **none possible** — Codex has no read-exclusion; `sandbox_mode` governs writes/network, not reads. Keep secrets outside the workspace. |
| Copilot | **not a committed file** — content exclusion is GitHub repo/org settings only, and doesn't cover the CLI/coding agent. |

Note: even where supported, ignore-file exclusion is best-effort and (on Gemini/Cursor) does **not** stop a *terminal* tool from `cat`-ing a secret — pair it with the command allow-list for real protection.

**Hooks.** klaussy ships two guards — a **git-commit guard** (runs format + lint before a commit) and a **read-injection guard** (scans file/fetch content for prompt-injection markers). The guard scripts are cross-agent and dialect-tolerant: they extract the command/path from any agent's hook payload and block via `exit 2` + stderr, which every supported agent honors. klaussy wires each guard to whatever events the agent's protocol exposes:

| Guard | Claude | Gemini | Cursor | Codex | Copilot |
|-------|--------|--------|--------|-------|---------|
| git-commit | ✅ | ✅ | ✅ | ✅ | ✅ |
| read-injection (local read) | ✅ | ✅ | ✅ | — | — |
| read-injection (web fetch) | ✅ | ✅ | — | — | — |

Codex exposes no pre-file-read hook event (only shell/tool execution), and Copilot's `preToolUse` is *fail-closed* (a crashing hook denies every tool call) with unconfirmed read-tool argument shapes — so for those two klaussy wires only the commit guard, and the guards are hardened to never crash (any parse error → allow). Config lands in each agent's native location: `.gemini/settings.json`, `.cursor/hooks.json`, `.codex/hooks.json`, `.github/hooks/klaussy-guards.json`.

**Cross-platform.** The guard scripts are pure-stdlib Python with a `#!/usr/bin/env python3` shebang. Copilot uses its native `bash`/`powershell` hook split, so it runs the right interpreter on any OS. Cursor execs the script directly via its shebang. Gemini and Codex run a shell-string command, so klaussy writes the interpreter for the OS it runs on (`python3` on macOS/Linux, `python` on Windows); a mixed-OS team should ensure that interpreter resolves on each machine (Windows users: the python.org launcher honors the shebang).

**Other caveats.** Codex's slash-prompt format is deprecated in favor of Skills, so klaussy emits Codex *Skills* (at `.agents/skills/`).

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
7. Translates the conventions and skills into each selected agent's native files — by default, all five (see [Multi-agent targets](#multi-agent-targets))

## Running klaussy

The CLI is agent-agnostic — `klaussy init` scaffolds whichever agents you target (all five by default). If you use Claude Code, klaussy can additionally run as a Claude Code plugin or MCP server:

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

The MCP server exposes these tools: `klaussy_init`, `klaussy_checklist`, `klaussy_skills`, `klaussy_settings`, `klaussy_status`.

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
