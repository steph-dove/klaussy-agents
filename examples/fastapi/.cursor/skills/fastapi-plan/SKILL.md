---
name: fastapi-plan
description: Use when the user wants a plan for a non-trivial task in this repo. Runs discovery, parallel exploration of the codebase, clarifying questions and parallel architectures, then checks the plan against the requirements and against the repo itself (an adversarial sub-agent) before writing an approved plan.md. Planning only: it stops at the approval gate and hands implementation to the implement skill. Also known as `klaussy-plan`.
---

> **Adapted for Cursor.**
>
> - This skill orchestrates parallel sub-agents using Claude's `Agent` tool / `subagent_type` syntax. Most coding agents now have their own parallel sub-agent or task mechanism (e.g. Cursor's `Task`, Codex's `spawn_agent`, Gemini subagents, Copilot's `task`) — use yours and translate the wording. If it truly has none, apply each lens or angle yourself, sequentially, and combine the findings.
> - Where it references "plan mode" or `ExitPlanMode`, use your agent's own plan/approval mode if it has one; otherwise present your plan and wait for explicit approval before editing any files.

You are planning a task in this repo. Follow these phases in order — do NOT skip Phase 3 (clarifying questions).

**This skill plans. It does not build.** It ends at the approved `plan.md`; the work itself belongs to **`fastapi-implement`**, and the whole plan-to-PR loop to **`fastapi-rest-of-the-owl`**. Do not start editing code here, however obvious the first step looks.

**Output file:** the approved plan is written to `plan.md` at the repo root. The implement skill reads it back as the source-of-truth checklist and ticks its boxes as work proceeds, so a fresh session can resume mid-task by re-reading it. The file is gitignored.

Use TodoWrite throughout: create one task per phase up front, mark each in_progress when starting and completed when done. The flow is long-running, and the todo list keeps the user oriented.

**Hard cap on sub-agents:** This skill spawns up to 2-3 explore agents (Phase 2), 2-3 architects (Phase 4) and 1 adversarial plan reviewer (Phase 6) — at most 7 `Agent` invocations total across the whole flow. Do NOT exceed that cap. If you find yourself wanting an 8th invocation (retrying a failed agent, spawning a "just one more" specialist), stop and summarize what you have for the user instead. Retries hide failures; extra specialists are scope creep.

## Phase 1 — Discovery

Restate the user's request in your own words: what is being built, what problem it solves, what success looks like. Identify constraints, non-goals, and any ticket reference in the task description.

**Surface-level ambiguity check** — before launching parallel exploration in Phase 2 (which costs 2-3 agent invocations), make sure you can answer all of these:
- Can you name the *thing being built* in one sentence (a feature, a fix, a refactor)?
- Do you know the *user-visible surface* it touches (an endpoint, a screen, a command)?
- Is success *observable* (a behavior change you could write a test for)?

If any answer is "no", ask the user before exploring. Phase 3 covers the deeper "what should error handling do" / "what about edge case X" questions; Phase 1 catches the "do I even know what they want" case so the parallel agents don't waste effort on the wrong target.

**Referenced-asset check — block, don't invent.** If the task or ticket points at material you need but cannot actually retrieve — a mockup, screenshot, or design file attached to a GitHub/Jira issue; a Figma link; an image, spec, or doc you have no tool to open — do NOT proceed by guessing what it contains. A ticket CLI (`gh issue view`, `glab issue view`, and the Jira equivalents) shows an issue's text but does not download its image attachments, and a design you can't see is not a design you can fabricate. Stop and tell the user exactly which assets you're missing and ask them to provide them (paste the image, drop the file into the repo, share the copy/measurements). Never make up UI text, layout, spacing, colors, or copy to fill the gap — a plausible-looking invention is worse than a blocked task, because it looks done. This is a hard block: planning cannot continue past a design the human hasn't given you.

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

Launch 2–3 architect subagents IN PARALLEL via the Agent tool with `subagent_type: general-purpose`. Pass each agent the architect process below + their priority + the user's task + the answers from Phase 3 + the key file paths from Phase 2 with one line of findings each. Don't paste the explore agents' full reports; architects read the files they need themselves, and every pasted report is paid for once per architect.

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

## Phase 5 — Write the plan

Still in plan mode. Write the chosen plan to `plan.md` at the repo root (and/or save it as an uncommitted OKF session note in `$KLAUSSY_SESSION_NOTES_DIR/<agent-name>-plan.md` with frontmatter `type: session-note` and `tags: [plan, design]`) using the structure below.

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

## Plan review
- <finding or uncovered requirement>: <what changed in the plan, or why not>
```

Resume rule: if `plan.md` already exists when this skill starts, ask the user whether to resume from it (pick up at the first unchecked box) or discard and start a new plan. Do not silently overwrite an in-progress plan.

## Phase 6 — Check the plan

Two checks, both before the user sees it. Neither is optional: a plan that reads well and doesn't survive contact with the repo is the expensive failure this skill exists to prevent.

**1. Against the requirements (you do this).** Go line by line:

- Every requirement in the task definition maps to at least one build step.
- Every Phase 3 decision shows up in the plan, or in Out of scope with a reason.
- Every build step traces back to a requirement — anything that doesn't is scope you invented; cut it.
- Verification covers each requirement. A requirement nobody can check isn't planned, it's hoped for.

**2. Against the repo (a sub-agent does this).** Launch ONE sub-agent via the Agent tool (`subagent_type: general-purpose`) to attack it. Pass it the path to `plan.md` and the list of key files from Phase 2, not their contents; it reads only what it needs to check a claim. Its prompt:

```
You are trying to break this implementation plan before anyone builds it. Read plan.md at <path>. Key files: <paths>.
Check each claim the plan makes about the code against the code itself. Look for: callers or
call sites the build sequence misses; a step that depends on something only a later step creates;
assumptions about behavior the code contradicts; an edge case or error path no step handles;
verification that wouldn't actually catch a regression; scope beyond the Phase 3 decisions.
Report at most 6 findings, worst first. Each finding: the plan step it breaks, file:line evidence,
and what the plan should say instead. A finding without code evidence is a guess, so drop it.
If the plan holds up, say so in one line. Do not write any files.
```

Weigh each finding on its evidence. Fix `plan.md` for the ones that hold, and record both checks in its `## Plan review` section: one line per finding with what changed, or why you didn't act on it, plus any requirement the first check found uncovered. Don't run a second round; this is one pass.

## Phase 7 — Approval gate

Output the complete plan in your chat response so the user can see it immediately. To prevent blocking or proceeding without review, you MUST end your turn here by calling no other tools (do NOT run the terminal command `ExitPlanMode` or make any edits yet). Ask the user to confirm the plan in the chat. Once the user replies to approve, run the terminal command `ExitPlanMode` in your next turn to register the plan with the desktop app, and then hand off.

## Hand off

Stop here. Say what the next step is and let the user take it:

- **Build it:** **`fastapi-implement`** works `plan.md` top-to-bottom, ticking each box as it lands.
- **Build, review, QA and open the PR:** **`fastapi-rest-of-the-owl`** runs the whole loop unattended.

## Anti-patterns to avoid (universal craft rules)

These apply regardless of the project. ALSO read this codebase's CLAUDE.md / `.claude/rules/*.md` / README / CONTRIBUTING early in Phase 2 to pick up project-specific rules and add them to your working list — local conventions usually beat generic advice when they conflict.

- Skipping Phase 3 because the task "seems clear." Most clear-looking tasks have hidden ambiguities. Ask anyway.
- Inventing design you can't see. When a ticket references an image or mockup you cannot download, block and ask for it (Phase 1) — never fabricate the UI text, layout, or copy to keep moving.
- Adding features, abstractions, or refactors beyond what the task requires. YAGNI.
- New abstractions for code with only one or two callsites. Three similar lines is fine.
- Backwards-compatibility shims for code that has no other callers.
- Comments that explain "what" the code does. Only "why," and only when it is non-obvious.
- Changing a public function, API, or return-shape without grepping all callers first.

## When NOT to use

- The task is a single-file, single-function bug fix — use debug or implement; the parallel-architect machinery here is overkill.
- The user has already produced a plan and just wants execution — use implement.
- The user wants the whole loop from task to open PR — use rest-of-the-owl, which calls this skill for its planning phase.
- The work is purely a refactor with no behavior change — use refactor, which establishes a test baseline first.

