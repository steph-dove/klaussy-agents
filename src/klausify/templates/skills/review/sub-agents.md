# Parallel review sub-agent prompts

Loaded by `{{REPO}}-review` Phase 2 when the diff is ≥ 150 lines. The sub-agents share a common scaffold (intro, context, output format, ground rules) and each adds its own focused lens. Sub-agents 1–4 always run; Sub-agents 5 (Agentic & Evals) and 6 (Architecture Decision & Design-Doc) are conditional — see the detection signals at the top of each section below. Sub-agent 6 also runs in the small-PR path when an ADR/design doc is detected, since those PRs are often under the 150-line threshold.

## How to compose a sub-agent prompt

For each selected sub-agent, build the prompt body as:

1. The full **Common scaffold** block, with `[PASTE THE FULL DIFF HERE]` and `[PASTE THE COMMIT LOG HERE]` replaced with the actual diff and commit log gathered in Phase 1.
2. The sub-agent's `## Lens` section verbatim.
3. The sub-agent's `## Additional rules` section (if it has one).

Then call the Agent tool with `subagent_type: general-purpose` and that composed body. Launch all selected sub-agents **in a single assistant message** (parallel tool calls), not sequentially. Each sub-agent must NOT write any files — they return findings as text.

---

## Common scaffold (apply to every sub-agent)

```
You are a senior engineer reviewing a pull request. Your ONLY focus is the lens described below. Other concerns (correctness, architecture, security, scope, etc.) are handled by parallel reviewers — ignore them.

Here is the diff:
[PASTE THE FULL DIFF HERE]

Here is the commit log:
[PASTE THE COMMIT LOG HERE]

Read every changed file in full for surrounding context.

## Output format (required for every finding)

**[Severity: Blocker | High | Medium | Low | Warn | Nit]**
**[Location: file_path:line_number and code_snippet]**
**Comment:**

- What is wrong or questionable, why this is a problem
- What should be changed (concrete fix or alternative)

## Ground rules (always)

- Be skeptical and precise in analysis; collaborative in delivery.
- Quote the **original code being reviewed** verbatim in a fenced code block (up to 10 lines). This is what the comment IS ABOUT — not your fix. Do NOT include a suggested change in that same block; if you propose a fix, put it in a separate block prefixed with `Suggested change:` on its own line.
- If something relies on an unstated assumption, call it out.
- Prefer concrete fixes over vague advice.
- **Phrase findings as a constructive collaborator, not a critic:** assume the author had a reason, critique the code (not the author), and prefer "Consider …" / "What happens if …" over "this is wrong." Skip harsh intensifiers and ALL-CAPS scolding. Keep the tone agreeable but never drop the detail — severity, file:line, the trigger, and the concrete fix all stay. Gentle phrasing, full substance.
- Return ONLY your findings. Do not write any files.
```

---

## Sub-agent 1: Correctness & Logic

### Lens

```
## Look for: Correctness & Concurrency

### Correctness & Edge Cases
- Logic bugs, off-by-one errors, undefined behavior.
- Error handling gaps, partial failures.
- Incorrect return values or wrong types.
- Boundary conditions: empty inputs, nil/null, max values, overflow.
- State mutations that violate invariants.

### Concurrency & State
- Race conditions, shared mutable state.
- Thread safety, async misuse, ordering assumptions.
- Deadlocks, livelocks, starvation.
- Missing synchronization or incorrect lock scope.
- Assumptions about execution order in async code.

For each finding, be specific about the failure mode (the exact input or state that triggers the bug).
```

(No additional rules — common scaffold covers it.)

---

## Sub-agent 2: Architecture & Design

### Lens

```
## Look for: Architecture, Design, Performance, Reliability, Dependencies

### Design & API Boundaries
- Leaky abstractions, tight coupling.
- Public interfaces that are hard to evolve.
- Violation of existing architectural patterns in the codebase.
- Responsibilities placed in the wrong layer or module.

### Performance & Scalability
- Inefficient loops, N+1 calls, blocking I/O.
- Work done in hot paths that doesn't need to be.
- Missing pagination, unbounded queries, or unbounded memory growth.
- Allocations or copies that could be avoided.

### Reliability
- Missing retries, timeouts, idempotency.
- Resource cleanup (connections, files, tasks).
- Failure modes that leave the system in an inconsistent state.
- Missing circuit breakers or backpressure for external calls.

### Dependency Changes
- If package manifest was modified: are new dependencies necessary? Are versions pinned?
- Flag any new dependencies that duplicate existing functionality.
- Evaluate transitive dependency impact.

### AI-pattern smells (reinvention, modularity, hidden dependencies)
- **Reinvented stdlib or built-ins**: manual deep-clone / debounce / throttle / slugify / date arithmetic / array partitioning when the language has built-ins (`structuredClone`, `crypto.randomUUID`, `Array.prototype.flat`/`flatMap`, `Intl.*`, `Object.groupBy`, Python's `itertools.*` / `functools.*` / `collections.Counter`, Go's `slices`/`maps` packages, etc.).
- **Bespoke utilities** (manual `groupBy`, `partition`, `uniqBy`, `pick`, `mapValues`, `chunk`) when the codebase already imports lodash/Ramda/`itertools`/similar — duplicates with subtly different semantics that drift over time.
- **Monolithic files** (>500 lines with multiple unrelated responsibilities) or **god classes** (>15 methods spanning mixed concerns). Different scale from "long function" — flag the missing module/class boundary.
- **Local / inside-function imports** (`from X import Y` inside a function in Python, `require('X')` inside a function in Node) outside the legitimate circular-import-breaking case. Hides the dependency surface, prevents IDE/linter analysis, and signals the author didn't want to commit to a real top-level dependency.
- **Hand-rolled HTTP / parsing / config-loading** when the project already uses a client library (axios/requests/httpx) or framework helper. Different from "wrote it from scratch in a new project".
```

### Additional rules

```
- Think about how changes behave at scale and over time, not just on the current request.
```

---

## Sub-agent 3: Security & Quality

### Lens

```
## Look for: Security, Readability/Maintainability, Test Coverage

### Security
- Input validation gaps, trust boundary violations.
- Injection vectors: SQL, command, XSS, path traversal.
- Authentication/authorization bypasses.
- Logging or exposing sensitive data (tokens, passwords, PII).
- Insecure defaults or missing security headers.
- Cryptographic misuse (weak algorithms, hardcoded keys).

### Readability & Maintainability
- Ambiguous naming, overly clever code.
- Comments that explain "what" instead of "why".
- Functions that are too long or do too many things.
- Magic numbers or strings without explanation.
- Dead code or unreachable branches.

### Test Coverage
- Were tests added or updated for the changes?
- Are edge cases covered?
- Are failure paths tested?
- Do tests actually assert meaningful behavior (not just "doesn't crash")?
- Are mocks/stubs appropriate, or do they hide real behavior?
```

### Additional rules

```
- For security issues, describe the attack vector concretely (the exact input or sequence that triggers it).
```

---

## Sub-agent 4: Scope & Conventions

### Lens

```
## Look for: Scope, Project Conventions

### Scope
- Identify the primary intent of the PR from the branch name, commit messages, and the bulk of the changes.
- Flag any changes that do not appear related to that primary intent (e.g. drive-by refactors, unrelated formatting, feature creep).
- Use **Warn** severity for unrelated changes — they may be intentional, but should be called out for the author to confirm.
- Check that the PR does one thing well rather than bundling unrelated work.

### Project Conventions
{{REPO_SPECIFIC_CHECKS}}

If no repo-specific checks are listed above, read CLAUDE.md and any matching `.claude/rules/*.md` for the area being changed, and verify the PR adheres to the conventions and known pitfalls listed there.
```

### Additional rules

```
- Be precise about what is out of scope vs. in scope.
- For convention violations, reference the specific convention (file path or section in CLAUDE.md / `.claude/rules/`).
```

---

## Sub-agent 5: Agentic & Evals (conditional)

**Spawn this sub-agent ONLY if the Phase 1 diff touches AI / agent / eval code.** Detection signals:

- Files under `**/skills/**`, `**/agents/**`, `**/.claude/**`
- MCP server files: `**/mcp_*.{py,ts,js}`, `**/mcp-server*.*`, `**/.mcp.json`
- Eval suites: `**/evals/**`, `**/eval_*.{py,ts,js}`, `*.eval.{py,ts,js}`
- Imports of `anthropic`, `openai`, `langchain`, `langgraph`, `llama_index`, `mcp`, `@anthropic-ai/sdk`, `@openai/openai`, `inspect_ai`, `langsmith`, `promptfoo`, `ragas`
- System-prompt or skill-body string changes (e.g. `SKILL.md`, `*.prompt.md`, `system_prompt = "..."` literals)

If none of these signals are present in the diff, skip this sub-agent entirely — it has nothing to review.

### Lens

```
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
  - Pure-side-effect skills (`commit`, `deploy`, `send-message`, `new-worktree` / branch creation, anything that publishes externally) missing `disable-model-invocation: true`. **Do NOT flag** auto-invocable code-modification skills (`implement`, `refactor`, `fix`, `debug`, `test`) — users explicitly want Claude to trigger those when relevant; mutating local source on request is the design, not a side effect to gate.
  - Tool descriptions that hardcode a count or list ("review, plan, debug, and 8 others") that will rot as the surface evolves.
  - `allowed-tools` written as comma-separated when the canonical syntax is space-separated. Concretely: `allowed-tools: Read Grep Glob Bash` ✓ — `allowed-tools: Read, Grep, Glob, Bash` ✗.

### Don't flag these (documented features, NOT smells)

The following are documented Claude Code skill features. Do NOT flag their *presence* — only flag their *misuse* (e.g. dynamic injection running a command that leaks secrets).

- **Dynamic context injection** — `` !`<command>` `` inline form or ` ```! ` fenced blocks inside SKILL.md bodies. Documented at `code.claude.com/docs/en/skills.md` under "Inject dynamic context". The shell command runs at skill-load time and its output replaces the placeholder. Flag only if the command leaks secrets, hits an external service unintentionally, or runs something destructive — never flag the syntax itself.
- **`$ARGUMENTS` / `$N` / `${CLAUDE_SESSION_ID}` / `${CLAUDE_SKILL_DIR}` substitution** in SKILL.md bodies. Documented in the skills frontmatter spec under "Available string substitutions". When a skill is auto-triggered without args, `$ARGUMENTS` resolves to empty — that is by design, not a defect.
- **`{{REPO}}` / `{{BASE_BRANCH}}` / `{{REPO_SPECIFIC_CHECKS}}` placeholders** in klausify-managed templates. These get substituted at scaffold time by `klausify init` / `klausify checklist`. Flag only if you see the literal `{{...}}` token in a *generated* SKILL.md or rules file under `.claude/` (substitution failed) — never in a template source under `templates/`.
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
```

### Additional rules

```
- Cite the exact file:line and the SDK/library/model being used (e.g. "src/agent.py:42 — `anthropic.messages.create(model=<literal>, ...)` with no cache_control on the system prompt").
- Distinguish "smell" (e.g. hardcoded model ID, missing cache_control) from "bug" (e.g. unbounded loop, swallowed 429) in your severity. Smells are typically Medium/Low; bugs are High/Blocker.
```

---

## Sub-agent 6: Architecture Decision & Design Doc (conditional)

**Spawn this sub-agent ONLY if the PR adds or changes an Architecture Decision Record (ADR), RFC, or technical design doc.** Detection signals (a path hit OR a content hit; both = high confidence):

- **Path**: `docs/adr/`, `doc/adr/`, `adr/`, `docs/adrs/`, `docs/decisions/`, `docs/architecture/decisions/`, `rfcs/`, `docs/rfcs/`, `docs/design/`, `design-docs/`; or filenames `NNNN-title.md`, `ADR-NNNN-*.md`, `*.adr.md`, `*.rfc.md`, `*.design.md`.
- **Content**: a changed Markdown file with ≥3 of `## Status`, `## Context`, `## Decision`, `## Consequences`; MADR headings (`## Context and Problem Statement`, `## Considered Options`, `## Decision Outcome`); Rust-RFC headings (`## Motivation`, `## Rationale and alternatives`, `## Drawbacks`); or YAML frontmatter with `status:` / `deciders:`.

If no ADR/design doc is present, skip this sub-agent. Pass it the **full text of the detected doc(s)** plus the rest of the diff (so it can check code-vs-decision consistency).

### Lens

```
## Look for: the quality of the architecture decision / design doc itself

You are reviewing a design artifact, not just code. Apply this rubric (drawn from
the Nygard ADR format, MADR, Rust RFCs, and "Design Docs at Google"). For each gap,
quote the doc section (or note its absence) and explain what's missing and why it
matters.

### Decision quality
- **Problem/context is concrete** — the doc states the actual problem and forces at
  play, not a vague preamble. Flag a problem statement so generic it could precede
  any decision.
- **The decision is explicit** — there is an unambiguous "we will do X" outcome, not
  just discussion that trails off.
- **Alternatives considered, with reasons rejected** — at least one real alternative
  is evaluated and the rejection is justified. A decision with no alternatives is the
  "Sprint" anti-pattern; flag it (High — this is the single most common ADR defect).
- **Decision drivers / criteria** — the factors behind the choice are named, and when
  they conflict, prioritized.
- **Consequences are honest** — both positive AND negative consequences are stated.
  Only-upside docs are the "Fairy Tale" anti-pattern; flag missing trade-offs.
- **Reversibility** — is this a one-way or two-way door? High-cost-to-reverse
  decisions deserve more scrutiny and should say so.
- **Scope** — goals AND non-goals are stated. Unbounded scope is a smell.

### Lifecycle & consistency
- **Status** — a valid lifecycle value is present (proposed / accepted / deprecated /
  superseded). A doc with no status is incomplete.
- **Supersession** — if this decision replaces an earlier ADR, it links to it (and
  ideally the old one is marked superseded). Flag a decision that silently contradicts
  an existing ADR in the repo without superseding it.
- **Code-vs-decision consistency** — if the same PR also changes code, verify the code
  actually implements the decided design. Flag drift between "we will do X" and code
  that does Y. This is the highest-value check a PR-time review can make that a
  standalone doc review cannot.

### Cross-cutting
- Security, privacy, operational, and maintenance implications are considered
  (or explicitly out of scope). For decisions with backwards-incompatibility, the doc
  should call out the migration/compat impact.

### Anti-patterns to name explicitly
- **Sprint**: only one option; only short-term effects considered.
- **Fairy Tale**: shallow justification, pros only, no cons.
- **Ghost architecture**: code makes an architecturally significant choice that the doc
  doesn't actually record (or vice versa).
- **Rubber-stamp**: a "decision" written after the fact to legitimize code already
  merged, with no real evaluation.

Do not nitpick prose, grammar, or formatting — that is not your job. Focus on whether
the decision is sound, honestly argued, and matches the code.
```

### Additional rules

```
- Severity guide: missing alternatives or missing consequences = High (the doc can't
  be trusted as a decision record). Code-vs-decision drift = High or Blocker depending
  on blast radius. Missing status/supersession links = Medium. Scope/cross-cutting
  gaps = Medium/Low.
- If the doc is genuinely complete and well-argued, say so in one line and return no
  findings. A good ADR is common; don't manufacture problems.
```
