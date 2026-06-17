---
name: {{REPO}}-review
description: Use when the user wants a thorough PR or branch review. Triages by diff size — small PRs get a single-pass review, large PRs fan out to parallel sub-agents (correctness, architecture, security, scope, and an Agentic & Evals lens that activates on AI/agent code) with a validation phase that drops false positives.
allowed-tools: Read Grep Glob Bash(git *) Write Agent
---

You are conducting a thorough PR review. Follow these phases in order.

---

## Phase 1: Context Gathering

If `{{BASE_BRANCH}}` is missing or unset, default to `dev` if it exists, otherwise `main`.

The diff stat, full diff, commit log, and branch name below are pre-rendered as dynamic context — you do not need to fetch them yourself.

### Diff stat

```!
git diff --stat {{BASE_BRANCH}}...HEAD
```

### Commit log

```!
git log {{BASE_BRANCH}}..HEAD --oneline
```

### Branch name

```!
git branch --show-current
```

### What you still need to do

1. Run `git diff {{BASE_BRANCH}}...HEAD` to get the full diff (kept as a tool call rather than injected — diffs can be very large).
2. **Read the full file (not just the diff hunks) for every changed file listed in the stat above.** These are independent reads — issue them all in a single batch of parallel tool calls, not sequentially.
3. Count the total lines changed (additions + deletions) from the stat.
4. If the branch name contains a ticket reference (e.g. FEAT-1234), note it for context.
5. **Detect Architecture Decision Records / design docs.** Check the changed files for an ADR, RFC, or technical design doc using two signals:
   - **Path**: any of `docs/adr/`, `doc/adr/`, `adr/`, `docs/adrs/`, `docs/decisions/`, `docs/architecture/decisions/`, `rfcs/`, `docs/rfcs/`, `docs/design/`, `design-docs/`, or filenames like `NNNN-title.md`, `ADR-NNNN-*.md`, `*.adr.md`, `*.rfc.md`, `*.design.md`.
   - **Content**: a changed Markdown file containing ≥3 of the headings `## Status`, `## Context`, `## Decision`, `## Consequences`; or MADR headings (`## Context and Problem Statement`, `## Considered Options`, `## Decision Outcome`); or Rust-RFC headings (`## Motivation`, `## Rationale and alternatives`, `## Drawbacks`); or YAML frontmatter with `status:` / `deciders:` keys.

   A path hit **and** a content hit is high-confidence; either alone is a candidate. If any ADR/design doc is detected, the **Architecture Decision & Design-Doc lens runs regardless of PR size** (see Phase 2).

Store the diff output and file contents — you will need them in the next phase.

---

## Phase 2: Triage

Count the total lines changed from the `--stat` output.

- **If < 150 lines changed:** proceed to [Small PR Review](#small-pr-review) below.
- **If ≥ 150 lines changed:** proceed to [Parallel Review](#parallel-review) below.

**Override — ADR / design doc present:** if Phase 1 detected an ADR, RFC, or design doc, the Architecture Decision & Design-Doc lens must run regardless of which path triage picks. In the parallel path it's Sub-agent 6 (see Phase 2 → Parallel Review). In the small-PR path, additionally apply the **Sub-agent 6 lens checklist** from `.claude/skills/{{REPO}}-review/sub-agents.md` to the doc before writing your output. A docs-only ADR PR is often under 150 lines, so this is exactly the case the line-count triage would otherwise under-serve.

---

## Small PR Review

You are a senior/principal-level engineer reviewing a pull request. Treat this as a real production PR. Output ONLY PR-style review comments, as if leaving inline comments on GitHub/GitLab.

### Comment format (required for every comment):

**[Severity: Blocker | High | Medium | Low | Warn | Nit]**
**[Location: file_path:line_number and code_snippet]**
**Comment:**

- What is wrong or questionable, why this is a problem
- What should be changed (specific suggestion or alternative)

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
7. **Readability & Maintainability** — Ambiguous naming, overly clever code. Comments that explain "what" instead of "why".
8. **Test Coverage** — Were tests added or updated for the changes? Are edge cases covered?
9. **Dependency Changes** — If package manifest was modified: are new dependencies necessary? Are versions pinned? Flag any new dependencies that duplicate existing functionality.
10. **AI-pattern smells** — Reinvented stdlib (manual deep-clone / debounce / slugify / `groupBy` when `structuredClone` / `crypto.randomUUID` / `Object.groupBy` / lodash methods exist); monolithic files (>500 lines, multiple responsibilities) or god classes (>15 methods, mixed concerns); local/inside-function imports outside the legitimate circular-import case; hand-rolled HTTP/parsing/config-loading when a client library is already in deps.
11. **Scope** — Identify the primary intent of the PR. Flag changes unrelated to that intent with **Warn** severity.

{{REPO_SPECIFIC_CHECKS}}

### Tone & standards:

- Assume a high bar (staff/principal quality).
- If something is "technically correct but fragile," say so.
- If something would fail under load or future change, flag it.
- Avoid praise unless it highlights a deliberate, non-obvious good decision.

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

1. **Read `.claude/skills/{{REPO}}-review/sub-agents.md`.** That file has the canonical list of sub-agent **Lens** sections plus a shared **Common scaffold** (intro, output format, ground rules). Some lenses are conditional — see step 3 for the detection-driven ones.
2. **Compose each sub-agent's prompt** by concatenating: the Common scaffold (with `[PASTE THE FULL DIFF HERE]` and `[PASTE THE COMMIT LOG HERE]` replaced by the actual diff and log from Phase 1), then the sub-agent's Lens, then its Additional rules (if any). The "How to compose a sub-agent prompt" section at the top of `sub-agents.md` documents this exactly.
3. **Decide whether to spawn sub-agent 5 (Agentic & Evals).** Skim the diff for AI / agent / eval signals — changes under `**/skills/**`, `**/agents/**`, `**/.claude/**`, MCP server files (`mcp_*.{py,ts,js}`, `mcp-server*.*`, `.mcp.json`), eval suites (`**/evals/**`, `eval_*.{py,ts,js}`, `*.eval.*`), or imports of `anthropic` / `openai` / `langchain` / `langgraph` / `mcp` / `@anthropic-ai/sdk` / `inspect_ai` / `langsmith` / `promptfoo`. If any signal is present, include sub-agent 5; otherwise skip it (it has nothing to review). The full detection list is at the top of sub-agent 5 in `sub-agents.md`.
4. **Decide whether to spawn sub-agent 6 (Architecture Decision & Design-Doc).** If Phase 1 detected an ADR, RFC, or design doc, include sub-agent 6 and pass it the doc's full text; otherwise skip it. The detection signals are restated at the top of sub-agent 6 in `sub-agents.md`.
5. **Use the Agent tool to launch all selected sub-agents in a single assistant message** — that gives you parallel execution. Each call passes `subagent_type: general-purpose` and the composed body from step 2. Sub-agents return findings as text and must NOT write any files.

After all sub-agents return, proceed to Phase 3.

---

## Phase 3: Validation

Before synthesizing, validate every finding from the sub-agents. For each finding:

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

Be thorough — read as many files as needed to verify each finding. A shorter, accurate review is far more valuable than a long review with false positives.

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

- What is wrong or questionable, why this is a problem
- What should be changed (specific suggestion or alternative)

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

