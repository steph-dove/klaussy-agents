# Lens: Agentic & Evals

## Look for: Agentic & Eval correctness

If, after reading the diff, you find no AI / agent / eval changes, return one line: "No agentic or eval changes — nothing to review." Do NOT invent findings.

### Agentic code (prompts, tools, model calls, agents, skills, MCP servers)

- **Hardcoded model IDs** — any literal model identifier (e.g. `<vendor>-<family>-<rev>` shapes like the current Claude / GPT / Gemini families) inline in code instead of routed through config. Models change; literals rot. Flag every literal that should be a config value.
- **Missing prompt caching** on stable prefixes (system prompts, tool/function definitions, skill bodies, long retrieved context). Anthropic SDK exposes this via `cache_control` breakpoints; OpenAI surfaces it automatically on the Responses API. Long stable prefixes that aren't cached are wasted tokens.
- **Unbounded agent loops** — recursion or `while True:` driving model calls with no max-iteration / max-cost guard. Cite the exit condition (or absence).
- **Token / context-window math** — system prompt + tools + history sized close to the model's window with no truncation strategy. Long static prefixes added to a chat history accumulator are a slow-burn defect.
- **Sensitive data sent to LLM** without redaction: PII, secrets, internal API URLs, customer-specific identifiers. Especially in tool descriptions, dynamic context injection (`` !`<command>` ``), and retrieved-document chunks.
- **Tool / function-call schema issues**: missing or wrong `required` fields; tool-name collisions across multiple registered tools; ambiguous parameter names. For Anthropic SDK tool definitions, descriptions exceeding 1,024 characters get truncated. For Claude Code skills, the combined `description` + `when_to_use` text is capped at 1,536 characters per skill (per `code.claude.com/docs/en/skills.md` frontmatter table).
- **LLM error paths quietly swallowed**: rate-limit (429) without retry/backoff, malformed-JSON parse, refusal, timeout, context-length-exceeded — bare `except:` / `catch (e)` blocks around an LLM call are almost always defects.
- **System prompt or skill body changed without a version bump** — silent behavior shifts. Look for prompt edits in the diff that don't bump a version constant, invalidate a cache, or note the change in CHANGELOG.
- **Streaming vs non-streaming**: long calls (>10s expected) made non-streaming where users see no progress; OR streaming used for short structured calls where the parsing overhead isn't justified.
- **Claude Code skill / MCP specifics**:
  - SKILL.md `description` doesn't start with "Use when…" (auto-trigger heuristic regression).
  - `allowed-tools: Bash` (unscoped) on a skill that only invokes git or one specific tool — flag e.g. a `commit` skill or `pr` skill with bare `Bash`. **Do NOT flag** unscoped `Bash` on skills that legitimately need to run user-defined test / lint / build / type-check commands (typically `debug`, `implement`, `refactor`, `test`, `fix`, `plan`); those genuinely cannot be enumerated up-front.
  - `disable-model-invocation: true` on a skill whose `description` starts with "Use when…". That description is the auto-trigger heuristic, so the two contradict: the skill advertises itself for model invocation and then refuses it. Klaussy's own side-effecting skills (`commit`, `pr`, `release`, `restack`, `new-worktree`, `split-pr`) gate in the body instead — they confirm the plan and never publish, push, or rewrite history without explicit approval in the request — which keeps them reachable by name while still asking first. Reserve the frontmatter flag for a skill that must never run unprompted even to propose something.
  - Tool descriptions that hardcode a count or list ("review, plan, debug, and 8 others") that will rot as the surface evolves.
  - `allowed-tools` written as comma-separated when the canonical syntax is space-separated. Concretely: `allowed-tools: Read Grep Glob Bash` ✓ — `allowed-tools: Read, Grep, Glob, Bash` ✗.

### Don't flag these (documented features, NOT smells)

The following are documented Claude Code skill features. Do NOT flag their *presence* — only flag their *misuse* (e.g. dynamic injection running a command that leaks secrets).

- **Dynamic context injection** — `` !`<command>` `` inline form or ` ```! ` fenced blocks inside SKILL.md bodies. Documented at `code.claude.com/docs/en/skills.md` under "Inject dynamic context". The shell command runs at skill-load time and its output replaces the placeholder. Flag only if the command leaks secrets, hits an external service unintentionally, or runs something destructive — never flag the syntax itself.
- **`$ARGUMENTS` / `$N` / `${CLAUDE_SESSION_ID}` / `${CLAUDE_SKILL_DIR}` substitution** in SKILL.md bodies. Documented in the skills frontmatter spec under "Available string substitutions". When a skill is auto-triggered without args, `$ARGUMENTS` resolves to empty — that is by design, not a defect.
- **Double-brace placeholders** in klaussy-managed templates: `REPO`, `BASE_BRANCH`, `REPO_SPECIFIC_CHECKS`, `HUMANIZE`, `FORGE`, and `PERMISSIONS_TARGET`, each wrapped in `{{` `}}`. These get substituted at scaffold time by `klaussy init` / `klaussy skills` / `klaussy checklist`. Flag only if you see a literal `{{...}}` token in a *generated* skill or rules file (substitution failed) — never in a template source under `templates/`.
- **Frontmatter fields** `name`, `description`, `when_to_use`, `allowed-tools`, `disable-model-invocation`, `user-invocable`, `model`, `effort`, `context`, `agent`, `hooks`, `paths`, `shell`, `argument-hint`, `arguments` — all documented in the skills frontmatter table. Don't flag a field's existence; flag wrong values.
- **Glob patterns inside `allowed-tools`** — `Bash(git diff *)` matches `git diff` with any args (`git diff`, `git diff --cached`, `git diff main...HEAD`, `git diff <file>`, multi-flag invocations, etc.). The `*` is a glob, not a literal. Do NOT flag a body command as "missing from allowed-tools" just because the literal flags don't appear inside the parentheses; the glob covers them. Only flag when the body invokes a *different command* (e.g. `git status` when allowed-tools has only `Bash(git diff *)`).
- **`.claude/rules/<name>.md` with YAML `paths:` frontmatter** — documented at `code.claude.com/docs/en/memory.md` under "Organize rules with .claude/rules/" → "Path-specific rules". Each rule file with `paths:` frontmatter loads only when Claude reads files matching the glob. Do NOT confuse this with Cursor's `.cursor/rules/*.mdc` (different tool, different format). Rule files without `paths:` load unconditionally alongside CLAUDE.md. Flag misuse (e.g. invalid YAML in the frontmatter, paths that don't match anything in the repo) but not the *presence* of this feature.

### Evals (test suites for LLM behavior)

- **Non-determinism** where avoidable: `temperature` not 0, no `seed` / `random_state`, no fixed eval harness seed. Flag any LLM call inside an eval that doesn't pin temperature.
- **Pass thresholds**: too high (>95%) → flaky and CI-noise generator; too low (<60%) → meaningless. Flag thresholds without a documented rationale.
- **No committed baseline / golden output** to diff against. Snapshot evals should have a checked-in expected output, not free-form "looks reasonable" assertions or LLM-as-judge calls without a calibrated rubric.
- **Coverage gaps**: happy-path evals only, no failure-mode / refusal / boundary-input / adversarial evals. The hard cases are where eval suites earn their keep.
- **Eval datasets not versioned** in source control — checked in as opaque blobs without provenance, or pulled from external URLs without a lockfile. A drifted dataset silently invalidates trend lines.
- **Cost guard missing**: an eval that spends real API credit per run with no max-call / max-token cap and no CI throttle. A flaky eval can cost real money.
- **Snapshot rot**: snapshot evals with stale `// updated: 2024-...` comments and no recent rebaseline. Stale snapshots silently mask regressions.
- **Eval not wired to CI** — only manual invocation. Means regressions ship.
- **LLM-as-judge without calibration**: using one LLM to grade another's output without a calibration set showing the judge's accuracy on known-good and known-bad outputs.

## Additional rules

- Cite the exact file:line and the SDK/library/model being used (e.g. "src/agent.py:42 — `anthropic.messages.create(model=<literal>, ...)` with no cache_control on the system prompt").
- Distinguish "smell" (e.g. hardcoded model ID, missing cache_control) from "bug" (e.g. unbounded loop, swallowed 429) in your severity. Smells are typically Medium/Low; bugs are High/Blocker.
