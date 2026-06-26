# <img src="brand-mark.png" width="32" height="32" align="absmiddle" alt="Klaussy Logo"> klaussy 🔍🤖

[![PyPI version](https://img.shields.io/pypi/v/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![Python versions](https://img.shields.io/pypi/pyversions/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Write once, align everyone.** Keep your conventions in one central `CLAUDE.md` and let `klaussy` compile it into native rules, settings, and skills for Claude, Gemini, Cursor, Copilot, Codex, Google Antigravity, and Cline.

Designed by an ex-GitHub, ex-Twitch, and ex-Microsoft engineer, `klaussy` is a multi-agent repository boilerplate generator. With a single command, it scaffolds conventions, repo-namespaced skills, stack-appropriate settings, and interactive guardrails for **seven major AI coding environments**—matching each agent's native file formats and capability profiles.

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

*Also bundles skills for `commit`, `pr`, `implement`, `refactor`, `explain`, `test`, and `new-worktree`.*

---

## ⚙️ How it Works under the Hood

1. **Discover:** Wraps `klaussy-repo-conventions` to auto-analyze your codebase and compile `CLAUDE.md`.
2. **Translate:** Parses rules and dynamically injects them into the `<repo>-review` skill so reviews check path-scoped rules.
3. **Scaffold:** Detects your stack (Python, Go, Node, Rust, Make) to generate custom permissions (`settings.json`, `config.toml`) and allowed tool prefixes.
4. **Isolate:** Writes `.cursorignore` and `.geminiignore` with secret-excluding patterns.

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
- `klaussy-repo-conventions >= 1.4.0`
- Claude Code CLI (optional, for `--init` enrichment)
- `mcp` (optional, for MCP server support)

---

## ⚖️ License & Governance
- **License:** MIT
- **Governance:** `klaussy` is an open-source project owned and maintained by Dovatech LLC (founded and owned by Stephanie Dover).
