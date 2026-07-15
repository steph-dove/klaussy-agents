---
name: {{REPO}}-plan
description: Use when the user wants to plan and implement a non-trivial task in this repo. Runs a multi-phase flow — discovery, parallel exploration, clarifying questions, parallel architectures, approval gate, implementation, parallel review, summary.
allowed-tools: Read Grep Glob Bash Write Edit TodoWrite Agent
---

You are helping plan and implement a task in this repo. Follow these phases in order — do NOT skip Phase 3 (clarifying questions).

**Output file:** the approved plan is written to `plan.md` at the repo root. Phase 6 reads it back as the source-of-truth checklist and updates checkboxes as work proceeds, so a fresh session can resume mid-task by re-reading `plan.md`. The file is gitignored.

Use TodoWrite throughout: create one task per phase up front, mark each in_progress when starting and completed when done. The flow is long-running, and the todo list keeps the user oriented.

**Hard cap on sub-agents:** This skill spawns up to 2-3 explore agents (Phase 2), 2-3 architects (Phase 4), and 3 reviewers (Phase 7) — at most 9 `Agent` invocations total across the whole flow. Do NOT exceed that cap. If you find yourself wanting a 10th invocation (retrying a failed agent, spawning a "just one more" specialist), stop and summarize what you have for the user instead. Retries hide failures; extra specialists are scope creep.

## Phase 1 — Discovery

Restate the user's request in your own words: what is being built, what problem it solves, what success looks like. Identify constraints, non-goals, and any ticket reference in the task description.

**Surface-level ambiguity check** — before launching parallel exploration in Phase 2 (which costs 2-3 agent invocations), make sure you can answer all of these:
- Can you name the *thing being built* in one sentence (a feature, a fix, a refactor)?
- Do you know the *user-visible surface* it touches (an endpoint, a screen, a command)?
- Is success *observable* (a behavior change you could write a test for)?

If any answer is "no", ask the user before exploring. Phase 3 covers the deeper "what should error handling do" / "what about edge case X" questions; Phase 1 catches the "do I even know what they want" case so the parallel agents don't waste effort on the wrong target.

**Referenced-asset check — block, don't invent.** If the task or ticket points at material you need but cannot actually retrieve — a mockup, screenshot, or design file attached to a GitHub/Jira issue; a Figma link; an image, spec, or doc you have no tool to open — do NOT proceed by guessing what it contains. `gh issue view` shows an issue's text but does not download its image attachments, and a design you can't see is not a design you can fabricate. Stop and tell the user exactly which assets you're missing and ask them to provide them (paste the image, drop the file into the repo, share the copy/measurements). Never make up UI text, layout, spacing, colors, or copy to fill the gap — a plausible-looking invention is worse than a blocked task, because it looks done. This is a hard block: planning cannot continue past a design the human hasn't given you.

Confirm with the user before continuing.

## Phase 2 — Understand (parallel exploration)

Launch 2–3 explore subagents IN PARALLEL via the Agent tool with `subagent_type: general-purpose`. Pass each agent BOTH the analysis approach AND the angle below in its prompt — they need that context inline because they don't see this master prompt. Mark this phase's todo in_progress when the agents are dispatched.

### Analysis approach (every explore agent uses this)

- **Feature Discovery**: Find entry points (UI components, IPC handlers, CLI commands). Locate core implementation files. Map feature boundaries and configuration.
- **Code Flow Tracing**: Follow call chains from entry to output. Trace data transformations at each step. Identify dependencies and integrations. Document state changes and side effects.
- **Architecture Analysis**: Map abstraction layers (presentation → business logic → data, or this project's equivalent — name them in terms of the codebase you actually find). Identify design patterns and architectural decisions. Document interfaces between components. Note cross-cutting concerns (auth, logging, caching).
- **Implementation Details**: Key algorithms and data structures. Error handling and edge cases. Performance considerations. Technical debt or improvement areas.

### Required output (every explore agent)

- Specific file:line refs for entry points and key components.
- Step-by-step execution flow with data transformations.
- A list of the 5–10 files most essential for understanding this surface.
- Strengths, issues, or opportunities relevant to the task.

### Per-agent angles

- Agent A — *Similar features*: "Find features in this codebase that already do something analogous to the user's task. Pick the closest match and trace its implementation comprehensively using the analysis approach above. Identify what we can reuse vs. what would need to change."
- Agent B — *Architecture & conventions*: "Map the architecture for the area this task touches using the analysis approach above. Identify existing patterns, naming conventions, and any project-doc guidelines (CLAUDE.md, README, CONTRIBUTING, AGENTS.md, etc.) that constrain or shape the solution."
- Agent C — *(when relevant)* UI / testing patterns: "Identify UI patterns, testing approaches, or extension points relevant to this task."

When the agents return, READ the key files they identified before designing. Agent summaries describe intent, not implementation — you will miss subtleties otherwise.

## Phase 3 — Clarifying questions (CRITICAL — do not skip)

List the ambiguities, edge cases, scope boundaries, error-handling preferences, and integration points the task description and Phase 1 confirmation did not specify. Present a clear, numbered list to the user and wait for answers before designing.

If the user replies "your call" or "no preference," commit to a recommendation and explicitly confirm it.

## Phase 4 — Design (parallel architectures, in plan mode)

**Enter plan mode now** — design and approval must happen before any edits. Stay in plan mode through Phase 5.

Launch 2–3 architect subagents IN PARALLEL via the Agent tool with `subagent_type: general-purpose`. Pass each agent the architect process below + their priority + the user's task + the answers from Phase 3 + the file list and findings from Phase 2 — they need all of that inline.

### Architect process (every architect uses this)

- **Pattern analysis**: Re-confirm the existing patterns and conventions you will integrate with. Cite file:line refs. Read any `.claude/rules/*.md` whose `paths:` glob matches the area you'll touch.
- **Architecture decision**: Pick ONE approach (do not hedge with "or maybe X"). State it clearly and own the trade-offs.
- **YAGNI rule**: Design the minimum surface that satisfies the task and Phase 3 answers. Do NOT add config knobs, extension hooks, abstractions for hypothetical future features, or "while we're here" cleanups. If the task doesn't ask for it, don't design it. Architect B (Clean architecture) may refactor more aggressively, but only when the existing structure actively blocks the task — never speculatively.
- **Component design**: Each component with file path, responsibilities, dependencies, interface signature.
- **Implementation map**: Specific files to create/modify with detailed change descriptions.
- **Data flow**: End-to-end flow from entry point through transformations to output/storage.
- **Build sequence**: Phased implementation steps as a checklist.
- **Critical details**: Error handling, state management, testing, performance, and security considerations relevant to this task.

### Per-architect priorities

- Architect A — *Minimal change*: smallest diff, maximum reuse of existing code, fewest new files. Refactor only when forced.
- Architect B — *Clean architecture*: clear abstractions, ergonomic for future change. May refactor more aggressively.
- Architect C — *Pragmatic balance*: speed + good-enough quality. Pick the best ideas from A and B without over-investing.

After agents return, present the user a brief summary of each blueprint, the trade-offs, and your recommendation with reasoning. Ask which they want.

## Phase 5 — Approval gate

Still in plan mode. Write the chosen plan to `plan.md` at the repo root using the structure below, and output the complete plan in your chat response so the user can see it immediately. To prevent blocking or proceeding without review, you MUST end your turn here by calling no other tools (do NOT run the terminal command `ExitPlanMode` or make any edits yet). Ask the user to confirm the plan in the chat. Once the user replies to approve, run the terminal command `ExitPlanMode` in your next turn to register the plan with the desktop app, and then proceed to Phase 6.

`plan.md` structure:

```markdown
# <task title>

<one-paragraph summary of what's being built and why>

## Decisions (from Phase 3)
- <ambiguity>: <chosen resolution>

## Build sequence
- [ ] <step 1 — file:line scope, concrete change>
- [ ] <step 2 ...>

## Out of scope
- <thing we explicitly aren't doing>

## Verification
- <how we'll know it works — tests, manual checks>
```

Resume rule: if `plan.md` already exists when this skill starts, ask the user whether to resume from it (pick up at the first unchecked box) or discard and start a new plan. Do not silently overwrite an in-progress plan.

## Phase 6 — Implementation

`plan.md` is the source-of-truth checklist. Work the unchecked boxes top-to-bottom in small, independently-shippable batches. After each batch:
- Update the checkbox in `plan.md` (`- [ ]` → `- [x]`) so a fresh session can resume.
- Update TodoWrite to mirror plan progress.
- Verify the code parses / compiles / lints (`node -c`, `tsc --noEmit`, `cargo check`, etc., as the language requires).
- Briefly state what changed (1–2 sentences).
- Pause if the next batch touches a different surface area or needs a separate user decision.

For UI work, do not report a feature as complete without manually exercising it — or, if you cannot (no fixture data, no running services, etc.), flag the verification gap explicitly.

## Phase 7 — Quality review (parallel)

After implementation, launch 3 reviewer subagents IN PARALLEL via the Agent tool with `subagent_type: general-purpose`. Pass each agent the reviewer process below + their focus + the diff (`git diff {{BASE_BRANCH}}...HEAD` or equivalent) + any context files they'll need.

### Reviewer process (every reviewer uses this)

- Read the diff AND the surrounding context (full file, callers, callees) — issues hide in the parts the diff does not show.
- Validate every finding by tracing the code path. Drop findings that are wrong because (a) the issue is already handled elsewhere, (b) the path is unreachable, (c) a framework guarantees the behavior, or (d) the concern is about unchanged code.
- For each surviving finding: severity (Blocker / High / Medium / Low / Nit), file:line + code snippet, what is wrong + why, what to do.
- Prefer a short accurate review over a long one with false positives.
- Flag only gaps that affect correctness or the stated requirements. Do NOT chase every possible improvement — a reviewer told to find gaps will always find some, and acting on them adds speculative abstractions, defensive code, and tests for cases that can't happen. That is over-engineering, not quality.

### Per-reviewer focuses

- Reviewer A — *Simplicity / DRY / readability*: Is the code as simple as it can be? Are there abstractions that should be inlined or duplications that should be extracted? Is naming clear? Are comments explaining "why" not "what"? Flag dead code and unreachable branches.
- Reviewer B — *Bugs, silent failures, inadequate error handling*. Apply these rules:
    - Empty `catch` blocks (e.g. `catch (_) {}`) are forbidden on user-initiated actions — the user clicked a button, they need feedback if it failed. They are also suspect on background work; even a 30s background poll should at least `console.error` the first failure of each tick.
    - Broad catches (`catch (Exception)`, `catch (e: any)`) hide unrelated errors. List every error type that could be silently swallowed.
    - Fallbacks must be explicit and justified. A fallback that returns `[]`, `null`, or "no data" on a parse error is indistinguishable from "no data was there" — surface a real error instead.
    - Error messages must be actionable. Generic strings ("Something went wrong") are defects.
    - Optional chaining (`?.`) and null coalescing (`??`) on critical operations can mask failures the same way an empty catch can — flag where they hide errors.
    - For each finding give: file:line, severity (CRITICAL silent failure / HIGH poor error message / MEDIUM could be more specific), what could be hidden, user impact, and a concrete fix.
- Reviewer C — *Project conventions and the anti-patterns below*: Did we hit any of the universal anti-patterns? Did we follow this project's docs (CLAUDE.md / README / CONTRIBUTING / equivalent)? Are public API shapes consistent? Are the project-specific invariants this codebase relies on still intact?

Consolidate findings, present high-severity issues to the user, and ask whether to fix now, defer to a follow-up, or proceed as-is.

## Phase 8 — Summary

Write a 3–5 line summary: what was built, key decisions, files modified, suggested next steps. Mark all TodoWrite tasks complete.

## Anti-patterns to avoid (universal craft rules)

These apply regardless of the project. ALSO read this codebase's CLAUDE.md / `.claude/rules/*.md` / README / CONTRIBUTING early in Phase 2 to pick up project-specific rules and add them to your working list — local conventions usually beat generic advice when they conflict.

- Skipping Phase 3 because the task "seems clear." Most clear-looking tasks have hidden ambiguities. Ask anyway.
- Inventing design you can't see. When a ticket references an image or mockup you cannot download, block and ask for it (Phase 1) — never fabricate the UI text, layout, or copy to keep moving.
- Adding features, abstractions, or refactors beyond what the task requires. YAGNI.
- New abstractions for code with only one or two callsites. Three similar lines is fine.
- Backwards-compatibility shims for code that has no other callers.
- Comments that explain "what" the code does. Only "why," and only when it is non-obvious.
- Changing a public function, API, or return-shape without grepping all callers first.
- Silent error swallowing in catch blocks that masks real failures from the user.
- Reporting UI work as complete without manually testing it (or explicitly flagging that you could not).

## When NOT to use

- The task is a single-file, single-function bug fix — use debug or implement; the parallel-architect machinery here is overkill.
- The user has already produced a plan and just wants execution — use implement and skip Phases 1–5.
- The work is purely a refactor with no behavior change — use refactor, which establishes a test baseline first.

