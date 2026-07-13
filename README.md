# <img src="brand-mark.png" width="32" height="32" align="absmiddle" alt="Klaussy Logo"> Klaussy-Agents

[![PyPI version](https://img.shields.io/pypi/v/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![PyPI downloads](https://img.shields.io/badge/downloads-2.3K%2B%2Fmonth-blue?logo=pypi&logoColor=white)](https://pypi.org/project/klaussy-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/steph-dove/klaussy-agents?style=flat&logo=github&label=Stars&color=blue)](https://github.com/steph-dove/klaussy-agents)

> **Write once, align everyone.** Keep your conventions in one central `CLAUDE.md` and let `klaussy` compile it into native rules, settings, and skills for Claude, Gemini, Cursor, Copilot, Codex, Google Antigravity, Cline, Aider, and OpenCode.

Designed by an ex-GitHub, ex-Twitch, and ex-Microsoft engineer, `klaussy` is a multi-agent repository boilerplate generator. With a single command, it scaffolds conventions, repo-namespaced skills, stack-appropriate settings, and interactive guardrails for **nine major AI coding environments**—matching each agent's native file formats and capability profiles.

> **📣 Out of stealth.** `klaussy` has been six months in the making — developed in private and hardened by a hands-on group of testers wiring it into their own repos and daily agent workflows. After months of iteration and real-world use, it's now open to everyone.

---

## ⚡ Quick Start

Get your repo ready for agent collaboration in seconds:

```bash
pip install klaussy-agents
cd your-repo
klaussy init
```

*Auto-detects your base branch and stack, then scaffolds all targets. To target specific agents, run `klaussy init --agents claude,cursor`.*

---

## 🤖 Supported Agents & Targets

`klaussy` translates your canonical repository conventions (`CLAUDE.md`) and workflows into native formats optimized for each agent's directory placement, scoping mechanisms, and capability boundaries:

*   **🤖 Claude Code**: Native `.claude/skills/`, `.claude/settings.json` allow/deny-lists, and active local read/fetch hooks.
*   **🌌 Google Antigravity**: Cross-agent `AGENTS.md` project-level rules, plugin-based path rules with glob triggers (`rules/*.md`), native hooks, and IDE-compatible permissions.
*   **💻 Cursor**: Interactive MDC rules (`.cursor/rules/*.mdc`) with auto-apply matching, terminal permissions allow-list, and `.cursorignore` read blocks.
*   **🐙 GitHub Copilot**: Instructions with custom `applyTo` file matchers (`.instructions.md`), and skills nested in `.github/skills/`.
*   **♊ Gemini CLI**: Hierarchical `GEMINI.md` scoping (loaded only when touching subdirectories), settings tool allow-lists, and `.geminiignore` filtering.
*   **📜 Codex CLI**: Structured `AGENTS.md` root-and-nesting rules, generic skills, and `.codex/config.toml` sandbox configurations.
*   **🧬 Cline**: `.clinerules/` Markdown rules with `paths:` glob activation, event-named `.clinerules/hooks/` guards (commit, read/web-injection, plan guidance), and `.clineignore` read blocks.
*   **🛩️ Aider**: Flat `CONVENTIONS.md` wired in via `.aider.conf.yml`'s `read:` key, `auto-lint`/`lint-cmd` + `test-cmd` gating, and `.aiderignore` read blocks. Model-agnostic — point it at any model, including a local Ollama one. (No skills/hooks: aider has neither mechanism.)
*   **🔓 OpenCode**: Root `AGENTS.md` conventions plus modular `.opencode/rules/*.md` path rules wired via `opencode.json`'s `instructions` glob, `.opencode/skills/`, last-match-wins `permission` read/bash rules in `opencode.json`, and a Bun plugin (`.opencode/plugins/klaussy.js`) that bridges tool hooks to the shared Python guards.

---

## 🛡️ Supercharged Hooks & Guardrails

`klaussy` installs cross-agent, dialect-tolerant guard scripts that intercept agent tool actions (terminal runs, file reads, web requests) at the boundary. They block unsafe commands via `exit 2` and stderr, which all supported agents respect:

### 1. Prompt-Injection Guard (`read_guard.py`)
> [!IMPORTANT]
> **Intercepts and neutralizes prompt injection.**
> Scans the content of any file being read locally or fetched from the web (on supported agents like Claude and Antigravity) for malicious instructions. Stops external data from hijacking your agent's current task context.

### 2. Comment Humanizer (`comment_guard.py`)
> [!TIP]
> **Keep commits and pull request comments clean.**
> Intercepts outgoing messages and pull request comments (e.g., `gh pr comment`). Automatically scrubs AI filler words, robotic formatting, and chatty openers, ensuring all generated communication reads like it was written by a human software engineer.

### 3. Pre-Plan Guidance (`plan_guidance.py`)
> [!NOTE]
> Injects strict guardrails (e.g., minimal lines changed, no over-engineering, write tests first) directly into the agent's plan step before it begins modifying files, preventing scope creep.

### 4. Git Commit Guard (`commit_guard.py`)
> [!NOTE]
> Automatically triggers your project's linting and formatting stack before allowing the agent to commit, keeping your Git history green.

### 5. Dependency Speed Bump (`dependency_guard.py`)
> [!NOTE]
> Catches package-manager commands that add a *new named* dependency (`pip install requests`, `npm install lodash`, `poetry add x`, …) and blocks once, asking the agent to confirm the package is actually needed and not coverable by the stdlib or an existing dep. Ignores manifest syncs (`npm ci`, `pip install -r`, `uv sync`) that add nothing new.

### 6. Self-Review Nudge (`self_review_guard.py`)
> [!NOTE]
> Prompts the agent to run a last-pass self-review of its own diff before declaring an implementation done, closing the loop with the `<repo>-self-review` skill.

---

## 🚀 Advanced Repository-Scoped Skills

Every generated skill is namespaced to your repo, carries an auto-trigger description, and is adapted to the agent's capability profile (such as mapping Claude's parallel subagent tools to Codex/Cursor/Antigravity equivalents):

| Skill | What it does | Magic Feature |
| :--- | :--- | :--- |
| **`<repo>-review`** | Senior-level PR review against the base branch. | 🧠 **Multi-Lens & Self-Refutation:** Runs parallel sub-agents looking at correctness, security, architecture, and agentic evals. A final validation phase filters out false positives before posting. |
| **`<repo>-debug`** | Rigid 5-phase bug resolution flow. | 🧪 **Test-First:** Reproduces the bug, writes a failing test, implements the fix, and runs the entire suite to verify. |
| **`<repo>-plan`** | Multi-phase planning and execution. | 📋 **Plan Gate:** Writes a detailed `plan.md` checklist and halts, waiting for your explicit approval before modifying files. |
| **`<repo>-precommit`** | Last-mile review of staged changes. | 🔍 **5-Lens Safety check:** Reviews changed lines only for silent failures, leaked secrets, debug leftovers, and verbose comments. |
| **`<repo>-humanize`** | Prose and documentation cleaner. | ✍️ **AI-Tell Scrubber:** Runs the deterministic `klaussy humanize` regex engine to strip chatbot scaffolding and formalisms. |
| **`<repo>-run`** | Launches and drives your app to watch a change work end-to-end. | 🚦 **Real-App Smoke Test:** Reads the run command from `CLAUDE.md`, backgrounds long-running servers until they're ready, then exercises the actual flow and reports what it saw — never patches code to make it start. |
| **`<repo>-security-audit`** | Focused security pass over the current change. | 🔐 **Threat-Lens Diff Scan:** Applies only the security lenses to the branch diff — leaked secrets, injection & SSRF, broken access control, unsafe deserialization, and vulnerable deps. Narrower and deeper than review; reports findings without refactoring. |
| **`<repo>-self-review`** | Last-pass review of your own diff before "done". | 🪞 **AI-Tell Catcher:** Checks the uncommitted change against a fixed list — reuse, stdlib, comments, dead code, tests, scope — catching what makes a diff read as AI-written before a human ever sees it. A companion hook nudges the agent to run it. |
| **`<repo>-qa`** | Captures PR-ready QA evidence for the current change. | 📸 **Change-Aware Verification:** Classifies the diff and runs only the QA that fits — screenshots for UI, exercised endpoints & e2e for backend, command output for a CLI, tests for a library — then saves artifacts to a `Downloads/<repo>-<branch>` folder where you can open them and writes a summary you can paste into the PR. |

*Also bundles skills for `commit`, `pr`, `implement`, `refactor`, `explain`, `test`, `new-worktree`, `fix`, `deps`, `address-review`, `document`, `release`, and `adr-generator`.*

<sub>🦉 And `<repo>-rest-of-the-owl` — hand it a task definition and it draws *the rest of the owl*: plans, implements, reviews and fixes, opens a humanized PR, then polls CI and code review, fixing findings and resolving threads until the PR is green and clean. Does everything except merge — the human keeps that button.</sub>

<sub>🥚 And `<repo>-slop-coded` — the evil twin of `humanize` that turns clean prose into maximal AI slop. For laughs and stress-testing the scrubber; never run it on a real deliverable.</sub>

---

## ⚙️ How it Works under the Hood

1. **Discover:** Wraps `klaussy-repo-conventions` to auto-analyze your codebase and compile `CLAUDE.md`.
2. **Translate:** Parses rules and dynamically injects them into the `<repo>-review` skill so reviews check path-scoped rules.
3. **Scaffold:** Detects your stack (Python, Go, Node, Rust, Make) to generate custom permissions (`settings.json`, `config.toml`) and allowed tool prefixes.
4. **Isolate:** Writes `.cursorignore` and `.geminiignore` with secret-excluding patterns.

---

## 🖥️ Cross-Platform Support

klaussy runs on **macOS, Linux, and Windows**. The guard scripts it installs are pure-stdlib Python that read stdin as UTF-8 (so a Windows `cp1252` locale never chokes on an em-dash) and resolve tools via `PATH` honoring Windows `PATHEXT` (so `.cmd` shims like `npm`/`eslint` run). The guard *logic* is portable on every agent.

What varies is whether a **single committed hook config** can launch the right Python interpreter for a teammate on a different OS — `python3` exists on macOS/Linux but not a stock python.org Windows install, which has `python`/`py`. This depends on each agent's hook format:

| Agent | Runs on Windows | Mixed-OS committed config | Mechanism |
| :--- | :---: | :---: | :--- |
| **GitHub Copilot** | ✅ | ✅ | native per-OS `bash` / `powershell` split |
| **OpenCode** | ✅ | ✅ | Bun plugin resolves the interpreter at runtime |
| **Codex CLI** | ✅ | ✅ | per-OS override: `command` (`python3`) + `commandWindows` (`py -3`) |
| **Claude Code** | ✅ | ⚠️ | OS-aware token + quoted `${CLAUDE_PROJECT_DIR}`; no per-OS command field exists, so the interpreter is fixed at scaffold time |
| **Gemini CLI** | ✅ | ⚠️ | self-expands `$GEMINI_PROJECT_DIR`; no per-OS field, so the interpreter is fixed at scaffold time |
| **Cursor** | ⚠️ | ⚠️ | docs don't specify the Windows shell or interpreter for hook commands |
| **Antigravity** | ⚠️ | ⚠️ | shell hook execution isn't documented; treat Windows as unverified |
| **Cline** | ❌ | — | Cline hooks are **macOS/Linux only** by spec; the guards are simply inert on Windows |
| **Aider** | ✅ | ✅ | no hook mechanism — nothing OS-specific to reconcile |

- **Single-OS teams: everything works.** The ⚠️ marks apply only to a repo scaffolded on one OS and then used by a teammate on another.
- ⚠️ **Claude / Gemini** still run on Windows — the interpreter token is just chosen from the *scaffolding* machine, so a mixed-OS team may need to adjust it (their configs have no per-OS field to do this automatically).
- Codex's Windows variant resolves the repo root via the same `git rev-parse` the POSIX command uses; it assumes a POSIX-compatible or PowerShell hook shell.

---

## 🔧 Installation & Usage

### As a CLI
```bash
pip install klaussy-agents
klaussy init
```

### As a Claude Code Plugin
```
/plugin marketplace add steph-dove/klaussy-agents
/plugin install klaussy@klaussy
```

### As an MCP Server
Add to your project's `.mcp.json`:
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

### Programmatic Python API
```python
from klaussy import toolkit

# Scaffold a repo programmatically
toolkit.init(repo=".", agents=["claude", "cursor"])
```

---

## 📋 Requirements
- Python 3.10+
- `klaussy-repo-conventions >= 1.5.0`
- Claude Code CLI (optional, for `--init` enrichment)
- `mcp` (optional, for MCP server support)

---

## 📜 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full release history. The latest release is **v0.14.0** (adds the `run` and `self-review` skills, plus `address-review`, `deps`, `document`, and `release`).

---

## ⚖️ License & Governance
- **License:** MIT
- **Governance:** `klaussy` is an open-source project owned and maintained by Dovatech LLC (founded and owned by Stephanie Dover).
