# Parallel review

Loaded by `fastapi-review` when triage finds 150 or more reviewable lines. The comment format, validation rubric, tone rules and "Write like a person" rules in the review SKILL.md still apply; this file adds the fan-out, validation and synthesis.

## Fan out to lens sub-agents

1. **Pick the lenses.** Correctness, Architecture, Security and Scope always run. Add **Agentic & Evals** only when the diff touches AI, agent or eval code:
   - files under `**/skills/**`, `**/agents/**`, `**/.claude/**`
   - MCP server files: `**/mcp_*.{py,ts,js}`, `**/mcp-server*.*`, `**/.mcp.json`
   - eval suites: `**/evals/**`, `**/eval_*.{py,ts,js}`, `*.eval.{py,ts,js}`
   - imports of `anthropic`, `openai`, `langchain`, `langgraph`, `llama_index`, `mcp`, `@anthropic-ai/sdk`, `@openai/openai`, `inspect_ai`, `langsmith`, `promptfoo`, `ragas`
   - system-prompt or skill-body string changes (`SKILL.md`, `*.prompt.md`, `system_prompt = "..."` literals)

   Add **Architecture Decision & Design Doc** when Phase 1 detected an ADR, RFC or design doc.
2. **Give each sub-agent a short prompt.** Every lens sub-agent reads its own instructions and fetches the diff itself, so its prompt is just:

   ```
   Review this pull request through one lens. Base branch: <base>.
   Read .gemini/antigravity-cli/plugins/klaussy/skills/fastapi-review/sub-agents.md, then
   .gemini/antigravity-cli/plugins/klaussy/skills/fastapi-review/lens-<name>.md, and follow them.
   Return only your findings. Do not write any files.
   ```

   The lens files are `lens-correctness.md`, `lens-architecture.md`, `lens-security.md`, `lens-scope.md`, `lens-agentic.md` and `lens-adr.md`. For the design-doc lens, add the doc paths to its prompt. Don't paste the diff, the scaffold or the lens text: each pasted copy is output you pay for once per sub-agent, and the sub-agent reads the files anyway.
3. **Launch all selected sub-agents in a single message** with the Agent tool (`subagent_type: general-purpose`), so they run in parallel.

**Model tiering (optional, if your sub-agent tool accepts a per-call model).** Run the mechanical Scope & Conventions lens on a fast, cheap model (e.g. `haiku`) and keep the reasoning-heavy lenses on the default model. Because the lenses run in parallel, this saves cost rather than wall-clock. No per-call model control? Run them all on the default model.

## Phase 3: Validation

Validate every finding before synthesis. The rubric lives in `.gemini/antigravity-cli/plugins/klaussy/skills/fastapi-review/lens-validation.md`; read it once.

- **More than 6 findings:** split them into batches of 4–6, grouped by file so each validator reads a file once. Spawn one validation sub-agent per batch, all in a single message. Its prompt is the base branch, the batch of findings verbatim, and "Read .gemini/antigravity-cli/plugins/klaussy/skills/fastapi-review/lens-validation.md and follow it. Write no files." Collect the survivors.
- **6 or fewer:** apply the rubric inline yourself; the fan-out isn't worth it.

## Phase 4: Synthesis

1. **Deduplicate.** When several lenses flagged the same issue, keep the most detailed comment and the highest severity.
2. **Sort by severity:** Blocker > High > Medium > Low > Warn > Nit.
3. **Cross-cutting check.** Look for issues spanning two lenses' domains, such as a correctness bug that is also a security hole, and add a combined comment if the lenses missed the intersection. Read only the files those findings point at; the lenses already read the rest.
4. **Assess overall quality** from the findings as a whole.

Write **REVIEW_OUTPUT.md** with each finding in the comment format from SKILL.md's Small PR Review, with a category after the severity. Categories: Correctness, Concurrency, Design, Performance, Reliability, Security, Readability, Tests, Dependencies, Scope, Conventions, Agentic, Evals, Design Decision. Keep any suggested diff verbatim, and phrase each comment in the delivery mode the user asked for (Collaborative by default, Blunt on request), following SKILL.md's Tone & standards and "Write like a person" rules.

### Final PR summary:

**Verdict:** Approve / Request Changes / Block · reviewed at `<short-sha>`

Then one line naming the issues that drive that verdict, and one line on test coverage. Nothing else — no restated finding list, no checkbox grid, no footer describing how the review was run.

Before writing `REVIEW_OUTPUT.md`, re-run the Phase 1 step 0 fetch and comparison. A large review takes long enough for the author to push again. If the branch moved, read the new commits (`git diff <reviewed-sha>..origin/<branch>`), update or drop the findings they fix, and stamp the new SHA.
