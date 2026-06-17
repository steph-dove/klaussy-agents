---
name: {{REPO}}-implement
description: Use when the user pastes a ticket, design doc, or task description and wants it implemented. Multi-phase flow — understand, investigate (in plan mode), plan, implement, verify. Enforces strict scope rules and writes failing tests first for bug fixes.
allowed-tools: Read Grep Glob Bash Edit Write
---

Here is the task to implement (the user described it in their message).

Do NOT start coding yet. Follow these phases in strict order.

## Phase 1: Understand the Task

Read the user's task description carefully. Identify:

1. **What is being asked** — the specific deliverable or behavior change.
2. **What is NOT being asked** — anything outside this scope is off-limits. Do not refactor, rename, restyle, or "improve" anything beyond the task. If you notice other issues, list them at the end but do NOT fix them.
3. **Acceptance criteria** — extract every testable condition from the task. If the task is ambiguous or missing details that would change your approach, ask the user to clarify before proceeding. Do not guess at requirements — wrong assumptions compound into wrong implementations.

---

## Phase 2: Investigate the Codebase

**Enter plan mode now.** Phases 2 and 3 must happen in plan mode to prevent premature edits.

Before touching any code, do a targeted read-only investigation. This is the most important phase — wrong file targets and wrong data sources are the #1 cause of wasted work. Investigate just enough to confirm you're targeting the right thing, then stop.

### Step 1: Orient

1. **Read CLAUDE.md** for project structure, conventions, and known pitfalls.
2. **Read any `.claude/rules/*.md`** whose `paths:` glob matches the area you'll edit. Path-scoped rules carry layer-specific conventions (API patterns vs. DB patterns vs. UI patterns) that the project-wide CLAUDE.md doesn't.
3. **Find the entry point.** Starting from the UI or API surface described in the task, grep for the route, component, or endpoint name. Read that file.
4. **Confirm the data source.** Read the actual query or ORM call that provides the data for this feature — do not assume. If there are multiple levels of indirection (service calls a repository calls a query), trace until you hit the actual data access.

### Step 2: Confirm direction

**Output what you've found so far:**
- The file(s) you believe need to change and why.
- The data source / query that provides the values.
- One similar feature in the codebase you'll use as a pattern (if any).

This is your checkpoint. If any of this is wrong, the rest of the work will be wrong too.

### Step 3: Targeted deep-dive

Only after confirming direction, go deeper on the files you'll actually change. **All four reads/greps below are independent** — issue them as a single batch of parallel tool calls (one assistant message containing multiple tool_use blocks), not as a sequential loop:

1. **Read each file you'll modify in full** — understand its structure, not just the function you'll edit.
2. **Grep for callers** of any function you plan to change. Skim the results — you need to know if your change will break a caller, not understand every caller in depth. If there are many callers, note that the function is high-traffic and plan accordingly.
3. **Find one existing pattern to follow.** Search for a similar feature already implemented — how is it structured, tested, and wired up? Match that pattern.
4. **Find existing tests** for the module you're changing. These are your regression guardrails and your template for new tests.

---

## Phase 3: Plan the Implementation

Still in plan mode. Design your approach before writing code. Keep it minimal — implement exactly what the task requires, nothing more.

1. **List the changes** — for each file, what you will add, modify, or remove. Be specific (function names, not "update the service").
2. **Flag risks** — if you found callers that could break, or edge cases the task doesn't mention, note them here.
3. **Tests first?** If this task is a bug fix or changes existing behavior, plan to write a failing test BEFORE writing the fix. This catches regressions immediately and proves the fix actually works. For new features, tests can come after.
4. **Check your scope.** Re-read the task description. Cross-reference every planned change against it. Remove anything that isn't directly required.

**Call `ExitPlanMode` to request approval.** Do NOT edit any files until the user approves; once they do, plan mode exits automatically and Phase 4 begins.

---

## Phase 4: Implement

Now write the code. Follow these rules strictly:

1. **Tests first for bug fixes.** If this is a bug fix or behavior change, write the failing test(s) now and run them to confirm they fail for the right reason. Then write the fix.
2. **One logical change at a time.** Don't batch unrelated edits into a single pass.
3. **Follow existing patterns.** Match the style, naming, structure, and conventions already in the codebase. Do not introduce new patterns unless the task explicitly requires it.
4. **Reuse existing code.** If a utility, helper, or base class exists for what you need, use it. Do not write a new abstraction for something that's already solved.
5. **Don't over-engineer:**
   - No feature flags, config options, or extension points unless the task asks for them.
   - No extra validation for scenarios that can't happen.
   - No new abstractions for one-time operations.
   - If three lines of straightforward code solve it, don't write a helper function.
6. **Don't under-engineer:**
   - Handle the error cases that realistically occur.
   - If the task involves data, verify you're reading from the correct source — re-check the actual query, not your assumption.
   - If the task changes behavior, make sure the change propagates everywhere it needs to (UI, API, tests, types).
7. **After each file edit,** re-read the file to verify the change looks correct in context.

---

## Phase 5: Verify

After implementation, verify your work before presenting it as done.

1. **Run the project's test suite** (check CLAUDE.md for the test command). Fix any failures.
2. **Run linters/formatters** if available. Fix any issues.
3. **Re-read every file you modified.** For each change:
   - Does it do what the task asked? Not more, not less?
   - Does it handle the edge cases you identified?
   - Could it cause a regression in existing behavior?
4. **Check your diff.** Run `git diff` and review every line. Remove:
   - Unrelated formatting changes.
   - Commented-out code.
   - Debug logging you added during development.
   - Any change not directly tied to the task.

---

## Scope Rules

These are non-negotiable:

- **Do NOT modify files that aren't required by the task.** If you notice something wrong in an unrelated file, note it in your summary but do not fix it.
- **Do NOT rename variables, functions, or files** unless the task specifically requires it.
- **Do NOT add comments, docstrings, or type annotations** to code you didn't change.
- **Do NOT refactor surrounding code** to be "cleaner" or "more consistent."
- **Do NOT add dependencies** without explicit justification tied to the task.
- **If the task says "add a button,"** add a button. Don't also redesign the layout, add animations, or create a reusable button component library.

## When NOT to use

- The task is a bug fix where the root cause isn't obvious — use the debug skill first to diagnose, then come back here with a confirmed plan.
- The task is "make this code cleaner / better-structured" with no behavior change — use refactor instead, which preserves behavior under a test baseline.
- The task is multi-feature, exploratory, or has no clear acceptance criteria — use plan first, which fans out parallel architects and surfaces clarifying questions before writing code.
