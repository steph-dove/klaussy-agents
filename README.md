<img src="brand-mark.png" width="72" align="right" alt="Klaussy-Agents logo">

# Klaussy-Agents

[![PyPI version](https://img.shields.io/pypi/v/klaussy-agents.svg)](https://pypi.org/project/klaussy-agents/)
[![PyPI downloads](https://static.pepy.tech/personalized-badge/klaussy-agents?period=total&units=international_system&left_color=grey&right_color=blue&left_text=downloads)](https://pepy.tech/project/klaussy-agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/steph-dove/klaussy-agents?style=flat&logo=github&label=Stars&color=blue)](https://github.com/steph-dove/klaussy-agents)

> **Write your conventions once.** Keep them in one `CLAUDE.md` and `klaussy` compiles it into the native rules, settings, and skills for Claude, Gemini, Cursor, Copilot, Codex (OpenAI), Google Antigravity, Cline, Aider, OpenCode, and Kimi, on GitHub, GitLab, and Bitbucket.

One command scaffolds conventions, repo-namespaced skills, settings that fit your stack, and guardrails for ten AI coding agents, each in that agent's own file formats and within what it can do. Built by an ex-GitHub, ex-Twitch, ex-Microsoft engineer.

> **Out of stealth.** `klaussy` spent six months in private, hardened by a group of testers who wired it into their own repos and daily agent work. Now it's open to everyone.

---

## Quick start

Two ways in. Both end with a klaussified repo.

**Let your agent do it.** `gh skill install` drops the entry-point skills into
whichever agent you already use, and they install the CLI for you if it isn't
there:

```bash
gh skill install steph-dove/klaussy-agents --all --agent claude-code
```

Then run `/klaussy-init` in your repo. `--agent` also takes `cursor`, `codex`,
`gemini-cli`, `github-copilot`, `opencode`, `kimi-cli` and others.
`gh skill install --help` has the full list.

**Or drive the CLI yourself:**

```bash
pip install klaussy-agents
cd your-repo
klaussy init
```

*It detects your base branch and stack, then scaffolds every agent. To pick agents, run `klaussy init --agents claude,cursor`.*

Then use the skills. Every one is namespaced to your repo, so in a repo called `payments-service` you'd hand a whole task to the owl:

```
/payments-service-rest-of-the-owl https://linear.app/acme/issue/PAY-1234
/payments-service-rest-of-the-owl add a --dry-run flag to the reconciler CLI
```

*A ticket link or a plain description both work. See [Using the skills](#using-the-skills) for the naming rule and the rest of the set.*

---

## Example output

Two open-source repos, scaffolded and committed so you can read what `klaussy init`
writes before you run it on your own code. No install needed:

| Example | Upstream | What to look at |
|---|---|---|
| [`examples/fastapi/`](examples/fastapi/) | [fastapi/fastapi](https://github.com/fastapi/fastapi) | [`CLAUDE.md`](examples/fastapi/CLAUDE.md): the discovered conventions, decision log, and pitfalls |
| [`examples/httpx/`](examples/httpx/) | [encode/httpx](https://github.com/encode/httpx) | [`CONVENTIONS.md`](examples/httpx/CONVENTIONS.md): the same source, flattened for Aider |

Worth opening: a [generated review skill](examples/fastapi/.claude/skills/fastapi-review/SKILL.md)
with the repo's own rules injected into it, the
[Copilot instructions](examples/fastapi/.github/copilot-instructions.md) with
`applyTo` matchers, and the [commit guard](examples/fastapi/.claude/hooks/git_commit_guard.py)
as it lands in a repo. Every supported agent's directory is in there.
[`examples/README.md`](examples/README.md) has the full map and how to reproduce it.

---

## Supported agents

`klaussy` writes your conventions (`CLAUDE.md`) and workflows in each agent's native format, puts them where that agent looks, and uses whatever scoping and hooks it supports:

* **Claude Code**: `.claude/skills/`, `.claude/settings.json` allow/deny lists, and local read/fetch hooks.
* **Google Antigravity**: `AGENTS.md` project rules, plugin-based path rules with glob triggers (`rules/*.md`), hooks, and IDE-compatible permissions.
* **Cursor**: MDC rules (`.cursor/rules/*.mdc`) that auto-apply by path, a terminal allow-list, and `.cursorignore` read blocks.
* **GitHub Copilot**: `.instructions.md` files with `applyTo` matchers, and skills in `.github/skills/`.
* **Gemini CLI**: nested `GEMINI.md` files that only load when the agent touches that directory, tool allow-lists in settings, and `.geminiignore` filtering.
* **Codex CLI (OpenAI)**: root and nested `AGENTS.md` rules, skills, and `.codex/config.toml` sandbox config.
* **Cline**: `.clinerules/` Markdown rules switched on by `paths:` globs, guards in `.clinerules/hooks/` named by event (commit, read/web injection, plan guidance), and `.clineignore` read blocks.
* **Aider**: a flat `CONVENTIONS.md` wired in through the `read:` key in `.aider.conf.yml`, `auto-lint`/`lint-cmd` and `test-cmd` gating, and `.aiderignore` read blocks. Works with any model, a local Ollama one included. No skills or hooks, because aider has neither.
* **OpenCode**: root `AGENTS.md` plus `.opencode/rules/*.md` path rules pulled in by the `instructions` glob in `opencode.json`, `.opencode/skills/`, last-match-wins `permission` rules for reads and bash, and a Bun plugin (`.opencode/plugins/klaussy.js`) that hands tool hooks to the shared Python guards.
* **Kimi Code CLI (Moonshot / Kimi K2)**: a flat `.kimi-code/AGENTS.md` and `.kimi-code/skills/`. Kimi doesn't read nested `AGENTS.md`, so path rules get inlined under their globs, with the pre-plan guidance appended. Hooks and permissions are the awkward part: Kimi **only** loads `[[hooks]]` and `[[permission.rules]]` from the user-level `~/.kimi-code/config.toml`. So klaussy commits the guards to `.kimi-code/hooks/` and writes paste-in snippets (`klaussy-hooks.toml`, `klaussy-permissions.toml`) next to them. Paste them once and the guards run in whichever repo the session is in.

**Models vs. agents.** These are *agent tools*, not model vendors. klaussy writes the files each tool reads, so what matters is the CLI or IDE you drive, not the model answering. If you're on GPT-5.x, point klaussy at **Codex CLI**, OpenAI's agent. Aider and OpenCode will run GPT, Claude, Gemini, Kimi, or a local Ollama model on the same scaffolding.

---

## Hooks and guardrails

`klaussy` installs guard scripts that sit between the agent and its tools (terminal commands, file reads, web requests). The same guards run on every agent and cope with each one's hook dialect. They block with `exit 2` and a message on stderr, which every supported agent respects.

### 1. Prompt-injection guard (`read_guard.py`)

Scans every file the agent reads, and on agents that support it (Claude, Antigravity) every page it fetches, for injected instructions, and stops them before they take over the task.

### 2. Comment humanizer (`comment_guard.py`)

Scrubs AI filler, robotic formatting, and chatty openers out of comments before they post, on GitHub (`gh pr comment`, `gh pr review`, `gh issue create`, …) and GitLab (`glab mr note`, `glab mr create`, `glab issue update`, …). On Claude the body gets rewritten in place and the cleaned command runs. Other agents get the post blocked once, with the humanized command handed back to re-run.

The scrubber only removes mechanical tells, says so, and points at the `<repo>-humanize` skill for anything that needs a rewrite. **Bitbucket isn't covered.** It has no comment CLI, so posts go through `curl` against the REST API, and a guard that silently missed half of those would be worse than none. Run `<repo>-humanize` before posting there.

### 3. Pre-plan guidance (`plan_guidance.py`)

Puts guardrails like minimal changes, no over-engineering, and tests first into the agent's plan step, before it edits any files, so scope doesn't creep.

### 4. Git commit guard (`commit_guard.py`)

**The last gate before an agent writes to your history.** It's not a linter wrapper. The checks run in order and the first failure blocks the commit:

| Gate | What it catches |
|---|---|
| **Secret scan** | Credentials headed for your history. Provider tokens get flagged on sight (AWS access keys, GitHub, GitLab, Bitbucket, Slack, Google API, Stripe live and OpenAI keys, private key blocks, Slack webhooks). Generic `api_key = "..."` assignments are gated on length and Shannon entropy, so a real key blocks and `password = "postgres"` doesn't. `os.environ` lookups, `${TEMPLATE}` holes, and `changeme`/`your-key-here` stand-ins pass. |
| **Commit message** | Subjects that aren't Conventional Commits, caught before the commit lands and needs amending. |
| **Format + lint** | Your project's own tools (`ruff`, `eslint`, …), scoped to the staged files. |
| **Commented-out code** | Dead code an agent parked in a comment "just in case" (`ruff --select ERA`). It flags and never deletes, so commented code you meant to keep stays. |
| **Verbose comments** | The narration tell. Blocks a comment longer than 2 sentences, 4+ prose comments in a row, or any single comment over 30 words. Two sentences leaves room for the claim and the why. A third is usually the code restated. `# noqa`, `@ts-ignore`, JSDoc, license headers, and bare URLs are exempt. |
| **Function-local imports** | The import written where the need came up instead of where it belongs (`import json` three frames deep). Same rule as ruff's `PLC0415`, but only on your changed lines, so a local import elsewhere in the file won't block you. A `# noqa` on the line keeps the ones that earn it, like breaking a cycle or deferring an optional dependency. |

**Only your staged files get judged.** klaussy's own checks (secrets, comments, imports) go further and only look at the *lines* you changed, so an old secret or comment block elsewhere in a file you touched won't block you. Your project's format and lint run on the whole staged file, same as anywhere else. The formatter never rewrites anything outside your diff.

**It fails open, on purpose.** A missing tool, a payload it can't parse, or any unexpected error lets the commit through, because a guard that crashed shut would deny *every* tool call on some agents. `git commit --no-verify` skips the gate, same as git's own hooks.

### 5. Dependency speed bump (`dependency_guard.py`)

Catches package-manager commands that add a *new named* dependency (`pip install requests`, `npm install lodash`, `poetry add x`, …) and blocks once, asking the agent to confirm it needs the package and can't get by with the stdlib or an existing dep. Manifest syncs that add nothing new (`npm ci`, `pip install -r`, `uv sync`) go straight through.

### 6. Self-review nudge (`self_review_guard.py`)

Tells the agent to run the `<repo>-self-review` skill over its own diff before it calls an implementation done.

---

## Repo-scoped skills

Every skill is namespaced to your repo, has a description the agent triggers on, and is adapted to what the agent can do (Claude's parallel subagents map to the Codex, Cursor, and Antigravity equivalents, for example). Skills that touch a ticket, a PR/MR, or CI also adapt to your host, which klaussy reads from `origin`. GitHub gets `gh pr` commands, GitLab gets `glab mr` commands and discussion semantics, and Bitbucket gets REST endpoints and pipeline checks. If klaussy can't tell the host (a self-hosted install on a neutral hostname), the skill tells the agent to ask instead of guessing at an API.

| Skill | What it does | How |
| :--- | :--- | :--- |
| **`<repo>-rest-of-the-owl`** | Takes a task definition all the way to a green, reviewed PR. | Plans, implements, writes tests, self-reviews and fixes, and QAs the change with evidence. Then it opens a humanized PR and polls CI and code review, fixing findings and resolving threads until the PR is green and clean. Long-running and autonomous. It does everything except merge, so you keep that button. |
| **`<repo>-review`** | Senior-level PR review against the base branch. | Parallel sub-agents look at correctness, security, architecture, and agentic evals. A validation pass drops false positives before anything posts. |
| **`<repo>-debug`** | Strict five-phase bug fix. | Reproduces the bug, writes a failing test, fixes it, and runs the whole suite. |
| **`<repo>-plan`** | Multi-phase planning and execution. | Writes a `plan.md` checklist and stops there until you approve it. No files change before that. |
| **`<repo>-precommit`** | Last-mile review of staged changes. | Looks only at changed lines, for silent failures, leaked secrets, debug leftovers, and verbose comments. |
| **`<repo>-humanize`** | Cleans up prose and docs. | Rewrites prose the way you'd say it to a colleague: contractions, verbs instead of noun phrases, no structure a short answer doesn't need. Then it runs the `klaussy humanize` regex scrubber as a backstop for the tells a prompt can't guarantee. |
| **`<repo>-run`** | Launches and drives your app to watch a change work end-to-end. | Reads the run command from `CLAUDE.md`, backgrounds long-running servers until they're ready, exercises the flow, and reports what it saw. It never patches code to get the app to start. |
| **`<repo>-security-audit`** | A focused security pass over the current change. | Applies only the security lenses to the branch diff: leaked secrets, injection and SSRF, broken access control, unsafe deserialization, and vulnerable deps. Narrower and deeper than review. It reports findings and doesn't refactor. |
| **`<repo>-self-review`** | Last-pass review of your own diff before "done". | Checks the uncommitted change against a fixed list (reuse, stdlib, comments, dead code, tests, scope) for whatever makes a diff read as AI-written, before a human sees it. A companion hook nudges the agent to run it. |
| **`<repo>-qa`** | Captures PR-ready QA evidence for the current change. | Classifies the diff and runs only the QA that fits: screenshots for UI, endpoint and e2e runs for backend, command output for a CLI, tests for a library. Artifacts go to a `Downloads/<repo>-<branch>` folder you can open, plus a summary you can paste into the PR. |
| **`<repo>-restack`** | Rebases a stack of dependent branches after the base moved or the bottom one landed. | `klaussy restack` works out the parent/child chain from git ancestry and reflogs (so an amended mid-stack parent still gets found) and saves it in `git config`, so it works on GitHub, GitLab, Bitbucket, or no forge at all. The model confirms the chain and resolves conflicts. The CLI does the git work. It records every branch tip as an undo path, rebases each branch `--onto` its new parent so a child never replays its parent's commits, force-pushes bottom-up with a lease, and checks the result with `range-diff`. Retargeting PR/MR bases is an optional last step per host, and when no CLI matches it prints the steps instead of failing. |
| **`<repo>-split-pr`** | Splits an oversized change into a stack of dependent PRs. | Strips comment bloat first, since a third of a "too big" diff is often narration. Then `klaussy split-prep` reads the layers off the import graph (Python through `ast`, JS/TS through its imports), so layer 1 provably imports nothing above it. Cycles get flagged as unsplittable, and files it can't graph are listed, not guessed at. It backs the original up to a `-prestack` branch before editing anything. `klaussy split-carve` then carves the layers, proves the top of the stack matches the source byte for byte, and runs your checks on every layer before a single push. Nothing gets created until you've confirmed the seams. |
| **`<repo>-grant-permissions`** | Stops the agent asking permission for every routine dev command. | Detects your stack, including `scripts/` and Makefile runners that a bare `Bash(pytest *)` rule misses, and writes an allow-list into each agent's own permission file. Tests, lint, build, git, and the package manager stop prompting, and secret files stay denied. It shows you the list before writing and never loosens anything quietly. Its limits: curated mode trusts the agent to run repo code, and per-tool denies don't stop Bash from reading secret files. Broad mode is opt-in. |

*There are also `commit`, `pr`, `implement`, `refactor`, `explain`, `test`, `new-worktree`, `worktree-cleanup`, `fix`, `deps`, `address-review`, `document`, `release`, `session-context`, and `adr-generator` skills.*

<sub>And `<repo>-slop-coded`, the evil twin of `humanize`, which turns clean prose into maximal AI slop. It's for laughs and stress-testing the scrubber. Don't run it on anything you're shipping.</sub>

---

## How it works

1. **Discover:** Runs `klaussy-repo-conventions` to analyze your codebase and write `CLAUDE.md`.
2. **Translate:** Parses the rules and injects them into the `<repo>-review` skill, so reviews check path-scoped rules.
3. **Scaffold:** Detects your stack (Python, Go, Node, Rust, Make) to generate permissions (`settings.json`, `config.toml`) and allowed tool prefixes. It also reads your host from `origin` and fills in the matching forge commands in the skills that need them.
4. **Isolate:** Writes `.cursorignore`, `.geminiignore`, `.clineignore`, and `.aiderignore` with secret-excluding patterns, on top of the deny rules in each agent's settings. Agents differ in how much they respect `.gitignore`, so klaussy does both.

---

## Cross-platform support

klaussy runs on **macOS, Linux, and Windows**, and the hooks are built so you don't have to think about the OS. The guards read stdin as UTF-8, so a Windows `cp1252` locale doesn't choke on an em-dash. They resolve tools through `PATH` and honor Windows `PATHEXT`, so `.cmd` shims like `npm` and `eslint` run.

The tricky part is that a committed hook command can't portably name a Python interpreter. `python3` is missing on a stock python.org Windows install, and `python` isn't guaranteed on Linux or macOS. So the guards launch through **`klaussy-hook`**, a pip console script that lands on `PATH` on every OS (`klaussy-hook.exe` on Windows) and runs the guard under klaussy's own interpreter. The committed command names no interpreter, so it works the same whichever machine scaffolded the repo. It adds nothing to install, since the comment and commit guards already need `klaussy` at runtime.

| Agent | Runs on Windows | Same config on any OS | Mechanism |
| :--- | :---: | :---: | :--- |
| **Claude Code** | ✅ | ✅ | `klaussy-hook` launcher (PATH-resolved) |
| **Gemini CLI** | ✅ | ✅ | `klaussy-hook` launcher; Gemini expands `$GEMINI_PROJECT_DIR` itself |
| **GitHub Copilot** | ✅ | ✅ | native per-OS `bash` / `powershell` split |
| **OpenCode** | ✅ | ✅ | Bun plugin resolves the interpreter at runtime |
| **Codex CLI** | ✅ | ✅ | per-OS override: `command` (`python3`) + `commandWindows` (`py -3`) |
| **Kimi Code CLI** | ✅ | ✅ | `klaussy-hook --repo-relative`; the launcher finds the repo root at run time |
| **Cursor** | ⚠️ | ⚠️ | docs don't say which shell or interpreter runs hook commands on Windows, so it's best-effort |
| **Antigravity** | ⚠️ | ⚠️ | shell hook execution isn't documented; treat Windows as unverified |
| **Cline** | ❌ | n/a | Cline hooks are **macOS/Linux only** by spec, so the guards do nothing on Windows |
| **Aider** | ✅ | ✅ | no hook mechanism, so nothing OS-specific to reconcile |

Codex's Windows variant finds the repo root with the same `git rev-parse` as the POSIX command. It assumes a POSIX-compatible or PowerShell hook shell.

Kimi's hooks live in the **user's** global config, so the command can't hardcode a repo path. Its four-field hook schema (an unknown key fails the whole config load) leaves no room for a per-OS override or a shell one-liner either. So `klaussy-hook --repo-relative <path>` finds the enclosing repo inside the launcher, and fails open in repos klaussy hasn't scaffolded. One global entry stays correct everywhere and does nothing where it doesn't apply.

---

## Installation and usage

### As a CLI
```bash
pip install klaussy-agents
klaussy init
```

### Using the skills

After `klaussy init` the skills live in your repo and you call them by name. The name is always `<your repo name>-<skill>`, lowercased, with anything that isn't a letter or digit turned into a hyphen. So `My_App` gets `my-app-review` and `Payments Service` gets `payments-service-review`.

You don't need to remember which repo you're in: every skill also answers to `klaussy-<skill>`, so "run klaussy-review" works the same as `/my-app-review`. The agent resolves the alias. The slash command is still the repo-namespaced one, because agents take it from the directory name.

```
/<your repo name>-rest-of-the-owl <task link or description>
```

Hand it a ticket URL or type the task out, and it runs the whole loop: plan, implement, test, self-review, QA with evidence, open a humanized PR, then poll CI and review until the PR is green. It stops before merging, so you keep that button.

The ones you'll reach for daily:

```
/<repo>-review                      # senior-level review of the branch
/<repo>-debug the checkout total is wrong for EU orders
/<repo>-restack                     # rebase a stack of dependent PRs
/<repo>-split-pr                    # carve a too-big branch into a reviewable stack
/<repo>-grant-permissions           # stop the agent asking about routine commands
```

Most skills also trigger on their own when the work matches. Describe a bug and `debug` picks it up. The ones that touch anything outside your working tree (`commit`, `pr`, `release`, `restack`, `split-pr`, `new-worktree`, `worktree-cleanup`) confirm the plan with you before they act, so you can name one in plain prose and it still won't run off on its own.

*On other agents the same skills land in that agent's own directory (`.cursor/skills/`, `.gemini/skills/`, `.opencode/skills/`, `.github/skills/`, `.agents/skills/`) and you invoke them however that agent invokes skills. The slash form above is Claude Code's.*

### With `gh skill install`

Covered in the [Quick start](#quick-start). It installs two skills,
`klaussy-init` and `klaussy-update`. Ask for either by name instead of `--all`.

The 28 repo-scoped skills aren't published this way on purpose. Each one is
namespaced to your repo and carries your conventions, base branch, and forge
commands, so `klaussy init` generates them rather than copying them in.

### As a Claude Code plugin
```
/plugin marketplace add steph-dove/klaussy-agents
/plugin install klaussy@klaussy
```
This brings the `klaussy-init` and `klaussy-update` skills plus the MCP server.
The plugin doesn't need klaussy installed first. Its server starts through a launcher
that uses your existing install if there is one, and otherwise pulls `klaussy-agents[mcp]`
through `uvx` or `pipx`. The launcher runs under `python3`, which python.org's Windows
installs call `python`, so on those, install klaussy directly.

### As an MCP server
The server lives behind the optional `mcp` extra, so ask for that rather than the
bare package. A plain install puts `klaussy-mcp` on PATH but leaves out what it
imports, and the client reports the crash only as a closed connection:

```bash
pip install 'klaussy-agents[mcp]'
```

Then add to your project's `.mcp.json`:
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

Nothing installed at all? Point the config at a runner and it resolves the
package on first use:
```json
{
  "mcpServers": {
    "klaussy": {
      "command": "uvx",
      "args": ["--from", "klaussy-agents[mcp]", "klaussy-mcp"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```
The Claude Code plugin already does this for you.

### Removing it

```bash
klaussy uninstall --dry-run   # show what would go
klaussy uninstall             # do it, after confirming
```

Removes the generated skills, guards, hooks and ignore files. `.gitignore` and
each agent's settings get *edited* rather than deleted, because klaussy merges
into those and they usually hold your own entries too. Anything klaussy can't
prove it wrote is reported and left alone. Conventions docs (`CLAUDE.md`,
`GEMINI.md`, `AGENTS.md`, `CONVENTIONS.md`) stay by default since people hand-edit
them. `--all` removes those too and returns the repo to how it was before klaussy.
The package stays installed either way. `pipx uninstall klaussy-agents` removes that.

There's a `/klaussy-uninstall` skill that runs the whole thing, including the
preview and the optional package removal.

### Python API
```python
from klaussy import toolkit

# Scaffold a repo programmatically
toolkit.init(repo=".", agents=["claude", "cursor"])
```

---

## Requirements
- Python 3.10+
- `klaussy-repo-conventions >= 1.6.0`
- Claude Code CLI (optional, for `--init` enrichment)
- `mcp` (optional, for the MCP server, via the `klaussy-agents[mcp]` extra)

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full release history, including what's in the current release.

---

## License and governance
- **License:** MIT
- **Governance:** `klaussy` is an open-source project owned and maintained by Dovatech LLC (founded and owned by Stephanie Dover).
