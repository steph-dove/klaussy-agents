---
name: httpx-review
description: Use when the user wants a thorough PR or branch review. Triages by diff size — small PRs get a single-pass review, large PRs fan out to parallel sub-agents (correctness, architecture, security, scope, and an Agentic & Evals lens that activates on AI/agent code) with a validation phase that drops false positives.
---

> **Adapted for Gemini CLI.**
>
> - This skill orchestrates parallel sub-agents using Claude's `Agent` tool / `subagent_type` syntax. Most coding agents now have their own parallel sub-agent or task mechanism (e.g. Cursor's `Task`, Codex's `spawn_agent`, Gemini subagents, Copilot's `task`) — use yours and translate the wording. If it truly has none, apply each lens or angle yourself, sequentially, and combine the findings.

You are conducting a thorough PR review. Follow these phases in order.

---

## Phase 1: Context Gathering

If `master` is missing or unset, default to `dev` if it exists, otherwise `main`.

The diff stat, full diff, commit log, and branch name below are pre-rendered as dynamic context — you do not need to fetch them yourself.

### Diff stat

Run `git diff --stat master...HEAD` and use its output.

### Commit log

Run `git log master..HEAD --oneline` and use its output.

### Branch name

Run `git branch --show-current` and use its output.

### What you still need to do

1. **Get the reviewable diff.** Run `klaussy review-prep --base master`. It returns the diff trimmed to reviewable files — lockfiles, generated/vendored trees, minified/binary blobs, and pure renames are dropped — followed by an **Excluded from review** manifest listing what it dropped and why. Use this trimmed diff as *the diff* for the rest of the review. If the `klaussy` CLI isn't on PATH (the command errors), fall back to `git diff master...HEAD` for the full untrimmed diff and proceed as before. Kept as a tool call rather than injected — even trimmed, diffs can be large.
2. **Read the full file (not just the diff hunks) for every *reviewable* changed file** — the files present in the trimmed diff, not the ones in the Excluded manifest. These are independent reads — issue them all in a single batch of parallel tool calls, not sequentially. The excluded files are deliberately out of scope: don't read or comment on them unless a finding in a reviewable file points directly at one.
3. Count the total **reviewable** lines changed — use the `N changed line(s)` figure in the review-prep summary line (on the `git diff` fallback, take the `--stat` total but ignore any lockfile / generated / vendored / minified / binary files).
4. If the branch name contains a ticket reference (e.g. FEAT-1234), note it for context.
5. **Detect Architecture Decision Records / design docs.** Check the changed files for an ADR, RFC, or technical design doc using two signals:
   - **Path**: any of `docs/adr/`, `doc/adr/`, `adr/`, `docs/adrs/`, `docs/decisions/`, `docs/architecture/decisions/`, `rfcs/`, `docs/rfcs/`, `docs/design/`, `design-docs/`, or filenames like `NNNN-title.md`, `ADR-NNNN-*.md`, `*.adr.md`, `*.rfc.md`, `*.design.md`.
   - **Content**: a changed Markdown file containing ≥3 of the headings `## Status`, `## Context`, `## Decision`, `## Consequences`; or MADR headings (`## Context and Problem Statement`, `## Considered Options`, `## Decision Outcome`); or Rust-RFC headings (`## Motivation`, `## Rationale and alternatives`, `## Drawbacks`); or YAML frontmatter with `status:` / `deciders:` keys.

   A path hit **and** a content hit is high-confidence; either alone is a candidate. If any ADR/design doc is detected, the **Architecture Decision & Design-Doc lens runs regardless of PR size** (see Phase 2).

Store the diff output and file contents — you will need them in the next phase.

---

## Phase 2: Triage

Count the total **reviewable** lines changed (from Phase 1 step 3 — the trimmed-diff figure, not the raw `--stat`, which still counts the dropped lockfile/generated/vendored noise).

- **If < 150 lines changed:** proceed to [Small PR Review](#small-pr-review) below.
- **If ≥ 150 lines changed:** proceed to [Parallel Review](#parallel-review) below.

**Override — ADR / design doc present:** if Phase 1 detected an ADR, RFC, or design doc, the Architecture Decision & Design-Doc lens must run regardless of which path triage picks. In the parallel path it's Sub-agent 6 (see Phase 2 → Parallel Review). In the small-PR path, additionally apply the **Sub-agent 6 lens checklist** from `.gemini/skills/httpx-review/sub-agents.md` to the doc before writing your output. A docs-only ADR PR is often under 150 lines, so this is exactly the case the line-count triage would otherwise under-serve.

---

## Small PR Review

You are a senior/principal-level engineer reviewing a pull request. Treat this as a real production PR. Output ONLY PR-style review comments, as if leaving inline comments on GitHub/GitLab.

### Comment format (required for every comment):

**[Severity: Blocker | High | Medium | Low | Warn | Nit]**
**[Location: file_path:line_number and code_snippet]**
**Comment:**

- What is questionable or risky, and why it matters
- What to change (specific suggestion or alternative)

### Review rules:

- Be skeptical and precise.
- Assume the code will be read and modified by others.
- Quote the **original code being reviewed** in a fenced code block — verbatim from the file, no edits or ellipses, no more than 10 lines. This is what the comment IS ABOUT, not what to do about it.
- Do NOT include a "fix" or "suggested change" in that same code block. If you have a concrete fix to propose, put it in a separate fenced block prefixed with `Suggested change:` on its own line above the block. Mixing the two confuses readers about which is which.
- If something relies on an unstated assumption, call it out.
- If behavior is unclear, treat that as a problem.
- Prefer concrete fixes over vague advice.
- **Precision over recall.** Default to *not* reporting. If no finding is one a competent author would clearly want to fix, return an empty review and say so — an empty review is a valid, good outcome, not a failure. Do not invent findings or pad to look thorough.
- **Every finding must name a concrete trigger.** State the specific input, state, or execution path that makes it go wrong. If you cannot describe how the problem is actually reached, you have not proven it — drop it.
- **Don't self-assign confidence scores.** A number you make up is noise; the trigger path above is the real evidence. Lead with the evidence, not a percentage.

### What to look for (in order of priority):

1. **Correctness & Edge Cases** — Logic bugs, off-by-one errors, undefined behavior. Error handling gaps, partial failures.
   - **Removed-behavior audit:** for every deleted or replaced line in the diff, name the invariant, guard, or behavior it enforced, then confirm the new code re-establishes it (or that dropping it is intentional and safe). Silently removed checks are a top source of regressions.
2. **Concurrency & State** — Race conditions, shared mutable state. Thread safety, async misuse, ordering assumptions.
3. **Design & API Boundaries** — Leaky abstractions, tight coupling. Public interfaces that are hard to evolve.
4. **Performance & Scalability** — Inefficient loops, N+1 calls, blocking I/O. Work done in hot paths that doesn't need to be.
5. **Reliability** — Missing retries, timeouts, idempotency. Resource cleanup (connections, files, tasks).
6. **Security** — Input validation, trust boundaries. Logging sensitive data.
7. **Readability & Maintainability** — Ambiguous naming, overly clever code. **Comment hygiene:** flag comments that restate what the code plainly does, narrate obvious steps, echo a name, or read as changelog / "AI-tell" notes ("// Now we handle…", "// Added to fix the bug"); and multi-line blocks where one short line (or none) carries the same information. The fix is delete it, or condense to a one-line WHY. Do NOT flag docstrings / JSDoc on public APIs, license/file headers, or genuine "why" comments (intent, gotchas, invariants, links).
8. **Test Coverage** — Were tests added or updated for the changes? Are edge cases covered?
9. **Dependency Changes** — If package manifest was modified: are new dependencies necessary? Are versions pinned? Flag any new dependencies that duplicate existing functionality.
10. **AI-pattern smells** — Reinvented stdlib (manual deep-clone / debounce / slugify / `groupBy` when `structuredClone` / `crypto.randomUUID` / `Object.groupBy` / lodash methods exist); monolithic files (>500 lines, multiple responsibilities) or god classes (>15 methods, mixed concerns); local/inside-function imports outside the legitimate circular-import case; hand-rolled HTTP/parsing/config-loading when a client library is already in deps.
11. **Scope** — Identify the primary intent of the PR. Flag changes unrelated to that intent with **Warn** severity.

### Repo Conventions
- File change hotspots: Frequently modified: `CHANGELOG.md`, `requirements.txt`, `_client.py`.
- Config access patterns: Manage environment configuration: Config access: 12 direct env accesses..
- Trunk-based/GitHub Flow: Trunk-based/GitHub Flow.
- PR template: PR template present.
- Python import path (flat-layout): flat-layout: `import httpx`.
- PEP 8 snake_case naming: Name functions, variables, and modules using snake_case style.
- Single test directory: tests/: All tests in 'tests/' directory.
- for `httpx/**/*.py`: Data classes: NamedTuple: Use NamedTuple for structured data. 2/2 structured classes use this pattern.
- for `httpx/**/*.py`: lowercase constant naming: Name constants using lowercase style.
- for `httpx/**/*.py`: Enum usage: Enum: Use Python enums for categorical values. Found 2 enum class(es). Types: Enum (1), IntEnum (1).
- for `httpx/**/*.py`: Custom decorator pattern: @click.option: Use custom decorator @click.option (17 usages).
- for `httpx/**/*.py`: Limited exception chaining: Preserve exception context: use `raise X from Y` or `raise X from None`.
- for `httpx/**/*.py`: Context manager usage: Manage resource lifecycles using context managers (e.g., Use context managers for resource management. 24 with statements. Types: http_client (5).).
- for `httpx/**/*.py`: Configuration via os.environ direct access: Use os.environ direct access.
- for `httpx/**/*.py`: High type annotation coverage: Standardize on typing: Type annotations are commonly used in this codebase. 396/396 functions have at least one type annotation..
- for `httpx/**/*.py`: Manual validation (ValueError/TypeError): Validate inputs and parameters: Use Manual validation (ValueError/TypeError) for input validation. 17/17 validation patterns use this approach..
- for `tests/**/*.py`: Test naming: Simple style (test_feature): Use Use Simple style (test_feature) naming. 523/539 test functions. Uses 2 test classes for grouping. naming style for all test functions.

### Verification Commands
Run these against the files this PR changed — not the whole repo. A repo-wide run buries the review in pre-existing violations from untouched files. Append the changed paths to each command (or use the tool's diff-aware mode); ignore findings outside this PR's diff:
- `pytest`

### Known Pitfalls
Flag if any of these are violated:
- 16 circular import dependencies detected — watch import order and avoid introducing new cross-module import cycles.
- CI/test flakiness fix or workaround: Fix client.send() timeout new Request instance (#3116)

### Tone & standards — pick a delivery mode, keep the substance:

Keep the analysis rigorous and the bar high (staff/principal quality); the mode below changes only *how* findings are delivered.

**Default to Collaborative.** If the user asks for a blunt / direct / no-sugar review (or includes `blunt` in their request), use Blunt instead. The substance guardrail applies to both.

**Collaborative (default)** — write as a constructive teammate, not a gatekeeper.
- Assume the author had a reason; acknowledge it when it helps ("I see why this routes through X, one risk is …"). Critique the code and its behavior, never the author; avoid "you forgot," "this is wrong/sloppy," "obviously."
- Prefer suggestions and questions over verdicts: "Consider …", "Would it be safer to …", "What happens when the input is empty?"
- Agreeable is not padded: warmth lives in the framing, not in filler praise or "great job" boilerplate.

**Blunt (on request)** — direct and terse. Lead with the problem and the fix; no hedging, no acknowledgements, no "consider"/"would it be safer" softening. Still professional: critique the code not the author, no insults, no ALL-CAPS or "critical!" melodrama. Brevity over warmth.

**Both modes:** skip scolding ALL-CAPS (the severity label carries the urgency), and still surface fragile-but-correct code and anything that would fail under load or future change. Tone is never a reason to go quiet on a real problem.

### Write like a person, not a chatbot

Whatever you output for the user (comments, descriptions, messages) must read as if a human engineer wrote it. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

- **No em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite. This is the single biggest AI tell.
- **No filler openers.** Cut "It's worth noting that", "It's important to note that", "I noticed that", "I wanted to point out that", "Please note that", "Just to mention", "Worth noting", "Note that". State the point directly.
- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps", "Feel free to...", "Happy to help", "Let me know your thoughts".
- **Tighten hedges.** "in order to" → "to"; "could potentially" → "could"; "may potentially" → "may". Drop stacked qualifiers.
- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**
- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **Don't mirror the thread's tone.** When you reply to an existing comment, review note, or message, read it for substance but not for temperature: neutralize any rudeness or bluntness in it before you draft. Hostile or curt input must not prime a hostile or curt reply, answer as if the other person had phrased it civilly.
- **Be short, then cut more.** Lead with the point. Keep the decision and the one fact that justifies it, then stop. A reply in a thread is usually one sentence; a single review comment one to five. Don't pad to sound thorough or stack throat-clearing ahead of the point.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop detail the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact; drop what's merely supporting. This is the one place humanizing may drop content, never reverse or invent meaning, but you need not preserve every clause.
- Vary sentence shape; don't open every line the same way. Never reword code, identifiers, or anything inside backticks or fences. Humanize prose only.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Good call, done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: Good call. `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

**Tone must not dilute substance.** Every comment keeps its severity, its `file:line` + verbatim code quote, its concrete trigger / failure scenario, and its specific suggested fix. Phrase it per the chosen mode; report it fully. A note that hides a real Blocker, downgrades severity, or drops the detail has failed.

### Validate findings:

Before writing the final output, validate every finding you produced. For each one:

1. **Read the full file** referenced in the finding (not just the diff hunk).
2. **Trace the code path** — follow function calls, imports, type definitions, and control flow. Read caller and callee files as needed.
3. **Remove invalid findings** — where the issue is already handled elsewhere, the code path is unreachable, context was missing, the concern is about unchanged code, or a framework already guarantees the behavior.
4. **Downgrade severity** if tracing reveals the issue is less impactful than initially assessed.

A shorter, accurate review is far more valuable than a long review with false positives.

### End of review:

After validation, add a final PR summary:

**Overall verdict:** Approve / Request Changes / Block

**Highest-risk issues:**
1. ...
2. ...
3. ...

**Test coverage assessment:**
- [ ] Adequate test coverage for changes
- [ ] Edge cases tested

Write this output to `REVIEW_OUTPUT.md`.

---

## Parallel Review

This PR is large enough to benefit from focused, parallel review.

1. **Read `.gemini/skills/httpx-review/sub-agents.md`.** That file has the canonical list of sub-agent **Lens** sections plus a shared **Common scaffold** (intro, output format, ground rules). Some lenses are conditional — see step 3 for the detection-driven ones.
2. **Compose each sub-agent's prompt** by concatenating: the Common scaffold (with `[PASTE THE FULL DIFF HERE]` and `[PASTE THE COMMIT LOG HERE]` replaced by the trimmed diff and commit log from Phase 1), then the sub-agent's Lens, then its Additional rules (if any). The "How to compose a sub-agent prompt" section at the top of `sub-agents.md` documents this exactly.
3. **Decide whether to spawn sub-agent 5 (Agentic & Evals).** Skim the diff for AI / agent / eval signals — changes under `**/skills/**`, `**/agents/**`, `**/.claude/**`, MCP server files (`mcp_*.{py,ts,js}`, `mcp-server*.*`, `.mcp.json`), eval suites (`**/evals/**`, `eval_*.{py,ts,js}`, `*.eval.*`), or imports of `anthropic` / `openai` / `langchain` / `langgraph` / `mcp` / `@anthropic-ai/sdk` / `inspect_ai` / `langsmith` / `promptfoo`. If any signal is present, include sub-agent 5; otherwise skip it (it has nothing to review). The full detection list is at the top of sub-agent 5 in `sub-agents.md`.
4. **Decide whether to spawn sub-agent 6 (Architecture Decision & Design-Doc).** If Phase 1 detected an ADR, RFC, or design doc, include sub-agent 6 and pass it the doc's full text; otherwise skip it. The detection signals are restated at the top of sub-agent 6 in `sub-agents.md`.
5. **Use the Agent tool to launch all selected sub-agents in a single assistant message** — that gives you parallel execution. Each call passes `subagent_type: general-purpose` and the composed body from step 2. Sub-agents return findings as text and must NOT write any files.

**Model tiering (optional, if your sub-agent tool accepts a per-call model).** The lenses don't all need the same horsepower. Run the mechanical lens — **Sub-agent 4: Scope & Conventions**, which is mostly pattern-matching intent and checking conventions — on a fast, cheap model (e.g. `haiku`), and keep the reasoning-heavy lenses (correctness, architecture, security, agentic, ADR) on the default/inherited model where judgment earns its keep. Because the sub-agents run in parallel, this mainly saves **cost** rather than wall-clock (the cheap lens was never the slowest); the latency win comes from the parallel validation in Phase 3. If your tool has no per-call model control, run them all on the default model — tiering is an optimization, not a requirement.

After all sub-agents return, proceed to Phase 3.

---

## Phase 3: Validation

Before synthesizing, validate every finding from the sub-agents. The rubric for a single finding is:

1. **Read the full file** referenced in the finding's location (not just the diff hunk).
2. **Trace the code path** — follow function calls, imports, type definitions, and control flow to understand the full context. Read caller and callee files as needed.
3. **Argue the author's side, then refute it.** For each finding, write the strongest one-line case that it is *not* a real problem (the input can't occur, a caller already guards it, the framework handles it). Then either refute that case with specific code evidence, or — if you can't — drop the finding as a likely false positive. A finding you can't defend against its own counterargument doesn't ship.
4. **Determine if the finding is still valid** given the full context. Common reasons a finding is invalid:
   - The issue is already handled elsewhere (e.g., validation happens in a caller, error is caught upstream).
   - The code path cannot actually be reached in the way the finding assumes.
   - The finding misreads the logic due to missing surrounding context.
   - The concern is about code that was not changed in this PR and is out of scope.
   - A dependency or framework already guarantees the behavior the finding questions.
5. **Remove invalid findings.** Do not include them in the final output. Do not note that they were removed.
6. **Downgrade severity** if tracing reveals the issue is less impactful than initially assessed (e.g., a "High" race condition that only affects a debug-only path should be "Low" or "Nit").

**Validate in parallel when there are enough findings.** Reading files and tracing paths one finding at a time is the slowest *serial* stretch of a large review — every other phase before it fanned out, but this one doesn't by default. So:

- **If the sub-agents returned more than 6 findings total:** partition them into batches of ~4–6 (group by file where you can, so a validator reads each file once) and spawn **one validation sub-agent per batch** with the Agent tool, all **in a single assistant message** (parallel). Compose each from `.gemini/skills/httpx-review/sub-agents.md` → **Validation sub-agent**, passing it that batch of findings plus the trimmed diff; it reads whatever caller/callee files it needs and returns only the survivors (with the rubric applied and any severity downgrades). Collect all survivors, then go to Phase 4. Each validator must NOT write files.
- **If there are 6 or fewer findings:** validate them inline yourself with the rubric above — the fan-out overhead isn't worth it.

A shorter, accurate review is far more valuable than a long review with false positives.

---

## Phase 4: Synthesis

After validation, synthesize the remaining findings:

1. **Deduplicate**: If multiple agents flagged the same issue, keep the most detailed comment and use the highest severity assigned.
2. **Sort by severity**: Blocker > High > Medium > Low > Warn > Nit.
3. **Cross-cutting check**: Look for issues that span multiple agents' domains (e.g., a correctness bug that is also a security vulnerability). Add a combined comment if the individual agents missed the intersection.
4. **Assess overall quality**: Consider the findings holistically.

Write the final output to **REVIEW_OUTPUT.md** in this format:

### Comment format (for each finding):

**[Severity: Blocker | High | Medium | Low | Warn | Nit]**
**[Location: file_path:line_number and code_snippet]**
**[Category: Correctness | Concurrency | Design | Performance | Reliability | Security | Readability | Tests | Dependencies | Scope | Conventions | Agentic | Evals | Design Decision]**
**Comment:**

- What is questionable or risky, and why it matters
- What to change (specific suggestion or alternative)

Phrase every comment in the delivery mode the user asked for (Collaborative by default, Blunt on request) and in a human voice — follow the **Tone & standards** guidance above, including the "Write like a person" rules — while preserving full detail (severity, location, trigger/failure scenario, concrete fix). Chosen-mode delivery, complete substance.

### Final PR summary:

**Overall verdict:** Approve / Request Changes / Block

**Highest-risk issues:**
1. ...
2. ...
3. ...

**Test coverage assessment:**
- [ ] Adequate test coverage for changes
- [ ] Edge cases tested

**Review method:** Parallel sub-agents (Agentic & Evals lens included only when the diff touches AI/agent/eval code)

---

## When NOT to use

- The user wants the diff *explained*, not critiqued — use the explain skill instead.
- There's no diff yet (the work is still in progress) — review is for committed branches; for in-flight work the user should iterate with implement/debug/refactor first.
- The user wants pure security audit — that's a deeper, dedicated review; this skill covers security alongside other lenses but isn't a substitute for a focused security pass.

