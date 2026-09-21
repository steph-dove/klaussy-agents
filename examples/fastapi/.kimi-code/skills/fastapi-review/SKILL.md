---
name: fastapi-review
description: Use when the user wants a thorough PR or branch review. Triages by diff size — small PRs get a single-pass review, large PRs fan out to parallel sub-agents (correctness, architecture, security, scope, and an Agentic & Evals lens that activates on AI/agent code) with a validation phase that drops false positives. Also known as `klaussy-review`.
---

> **Adapted for Kimi Code CLI.**
>
> - This skill orchestrates parallel sub-agents using Claude's `Agent` tool / `subagent_type` syntax. On Kimi Code CLI, use Kimi's own sub-agents: the `Agent` tool spawns one per subtask and `AgentSwarm` launches a batch of them, so the fan-out is real — launch all the lenses/validators at once rather than applying them sequentially.

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

0. **Confirm you're reviewing the latest push.** A review of commits the author has since replaced is wasted, and one of commits never pushed comments on code the request doesn't contain. Run `git fetch origin <branch>`, then compare `git rev-parse HEAD` with `git rev-parse origin/<branch>`:
   - **Same commit:** note the short SHA; the review is of that commit.
   - **Local is behind** (`git merge-base --is-ancestor HEAD origin/<branch>` succeeds): stop and tell the user the checkout is stale. Review after they pull; don't pull for them.
   - **Local is ahead or has diverged:** say so, name the unpushed commits (`git log --oneline origin/<branch>..HEAD`), and ask whether to review local HEAD or the pushed commit.
   - **No remote branch:** the branch was never pushed. Review local HEAD and say so in the verdict.
1. **Get the reviewable diff.** Run `klaussy review-prep --base master`. It returns the diff trimmed to reviewable files — lockfiles, generated/vendored trees, minified/binary blobs, and pure renames are dropped — followed by an **Excluded from review** manifest listing what it dropped and why. Use this trimmed diff as *the diff* for the rest of the review. If the `klaussy` CLI isn't on PATH (the command errors), fall back to `git diff master...HEAD` for the full untrimmed diff and proceed as before. Kept as a tool call rather than injected — even trimmed, diffs can be large.
2. **Don't read the full files yet.** The small-PR path reads them next; on the parallel path each lens reads what it needs, so reading them here too would pay for every file twice.
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

**Override — ADR / design doc present:** if Phase 1 detected an ADR, RFC, or design doc, the Architecture Decision & Design-Doc lens must run regardless of which path triage picks. In the parallel path it's the design-doc lens. In the small-PR path, additionally read `.kimi-code/skills/fastapi-review/lens-adr.md` and apply its checklist to the doc before writing your output. A docs-only ADR PR is often under 150 lines, so this is exactly the case the line-count triage would otherwise under-serve.

---

## Small PR Review

You are a senior/principal-level engineer reviewing a pull request. Treat this as a real production PR. Output ONLY PR-style review comments, as if leaving inline comments on GitHub/GitLab/Bitbucket.

**Read the full file (not just the diff hunks) for every *reviewable* changed file** — the files present in the trimmed diff, not the ones in the Excluded manifest. These are independent reads — issue them all in a single batch of parallel tool calls, not sequentially. The excluded files are deliberately out of scope: don't read or comment on them unless a finding in a reviewable file points directly at one.

### Comment format (required for every comment):

One finding is a metadata line, then the comment as plain prose:

```
**Blocker · Correctness · `src/api/session.py:88`**

The retry loop eats the 429, so a rate-limited call comes back looking fine. Rethrow after the last attempt.
```

Severities: Blocker, High, Medium, Low, Warn, Nit.

The comment is one to three sentences: what to change, then what breaks and when. Lead with the fix so a reader who stops after one sentence can still act. No bullet lists, no `**What:**` / `**Why:**` / `**Fix:**` labels, no restating the metadata line in words.

**One entry per problem, not per location.** Unrelated findings get their own entries even when they share a file. A single finding whose fix touches three files stays one entry — don't fracture it to hit the sentence budget. Ask whether the reader would act on the parts separately.

### Review rules:

- Be skeptical and precise.
- Assume the code will be read and modified by others.
- Quote the **original code being reviewed** only when `file:line` alone won't tell the reader what you mean, and then quote the smallest slice that shows the problem (5 lines or fewer), verbatim from the file with no edits or ellipses. This is what the comment IS ABOUT, not what to do about it.
- Do NOT include a "fix" or "suggested change" in that same code block. If you have a concrete fix to propose, put it in a separate fenced block prefixed with `Suggested change:` on its own line above the block. Mixing the two confuses readers about which is which.
- If something relies on an unstated assumption, call it out.
- If behavior is unclear, treat that as a problem.
- Prefer concrete fixes over vague advice.
- **Precision over recall.** Default to *not* reporting. If no finding is one a competent author would clearly want to fix, return an empty review and say so — an empty review is a valid, good outcome, not a failure. Do not invent findings or pad to look thorough.
- **Every finding must name a concrete trigger.** State the specific input, state, or execution path that makes it go wrong. If you cannot describe how the problem is reached, you have not proven it — drop it.
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
- File change hotspots: Frequently modified: `release-notes.md`, `uv.lock`, `pre-commit.yml`.
- Config access patterns: Manage environment configuration: Use `pydantic_settings` for env config.
- Gitmoji commits: Gitmoji commit messages.
- Trunk-based/GitHub Flow: Trunk-based/GitHub Flow.
- Response envelope classes: Use response envelope classes (3 found).
- Cursor-based pagination: Use cursor-based pagination. 4 cursor/after/before usages.
- Caching: functools.lru_cache: Use functools.lru_cache for caching.
- Python import path (flat-layout): flat-layout: `import fastapi`.
- PEP 8 snake_case naming: Name functions, variables, and modules using snake_case style.
- Distributed test files: Test files spread across 2 directories. 504 total test files.
- High type annotation coverage: Standardize on typing: Type annotations are commonly used in this codebase. 414/418 functions have at least one type annotation..
- for `fastapi/**/*.py`: URL-based API versioning: Use URL path versioning (e.g., /v1/, /api/v2/).
- for `fastapi/**/*.py`: Data class style: Pydantic for API + dataclasses for internal: Use Pydantic for API schemas (40) and dataclasses for internal DTOs (11). Good separation.
- for `fastapi/**/*.py`: Background jobs with FastAPI BackgroundTasks: Use FastAPI BackgroundTasks for background task processing.
- for `fastapi/**/*.py`: Data classes: Pydantic models: Use Pydantic models for structured data. 62/81 structured classes use this pattern.
- for `fastapi/**/*.py`: lowercase constant naming: Name constants using lowercase style.
- for `fastapi/**/*.py`: Enum usage: Enum: Use Python enums for categorical values. Found 4 enum class(es).
- for `fastapi/**/*.py`: Custom decorator pattern: @deprecated: Use custom decorator @deprecated (4 usages). Also uses: @asynccontextmanager.
- for `fastapi/**/*.py`: Limited exception chaining: Preserve exception context: use `raise X from Y` or `raise X from None`.
- for `fastapi/**/*.py`: Mixed validation approaches: Validate inputs and parameters: Use multiple validation approaches: Pydantic validation, Manual validation (ValueError/TypeError), Decorator-based validation..
- for `scripts/**/*.py`: Context manager usage: Manage resource lifecycles using context managers (e.g., Use context managers for resource management. 37 with statements (23 sync, 14 async). Types: file_io (4), threading (2).).
- for `scripts/**/*.py`: Structured configuration with Pydantic Settings: Use Pydantic BaseSettings for configuration management.
- for `tests/**/*.py`: FastAPI-style session dependency injection: Use get_db() dependency pattern with Depends() for session lifecycle.
- for `tests/**/*.py`: HTTP errors raised in service layer: HTTPException is frequently raised outside the API layer.
- for `tests/**/*.py`: Semi-centralized exception handling: Exception handlers are spread across 2 modules.
- for `tests/**/*.py`: OAuth2 authentication: Use OAuth2 for authentication. OAuth2 usages: 13.
- for `tests/**/*.py`: Mocking with pytest monkeypatch fixture: Use pytest monkeypatch fixture for test mocking. Also uses: unittest.mock / Mock, @patch decorator.
- for `tests/**/*.py`: Test naming: Simple style (test_feature): Use Use Simple style (test_feature) naming. 2253/2314 test functions. naming style for all test functions.

### Verification Commands
Run these against the files this PR changed — not the whole repo. A repo-wide run buries the review in pre-existing violations from untouched files. Append the changed paths to each command (or use the tool's diff-aware mode); ignore findings outside this PR's diff:
- `PYTHONPATH=./docs_src pytest -n auto --dist loadgroup tests`
- `pytest`
- `bash scripts/test-cov-html.sh # writes`
- `mypy fastapi`

### Known Pitfalls
Flag if any of these are violated:
- 20 circular import dependencies detected — watch import order and avoid introducing new cross-module import cycles.
- CI workflow `pre-commit.yml` contains steps allowed to fail (`continue-on-error: true`).
- `pytest` config sets `filterwarnings = ["error"]` — any warning raised during a test (including from dependencies) fails it. Deprecated-library tests (`orjson`, `ujson`) are only installed under the `test-deprecation` CI matrix leg specifically to exercise the deprecation warnings deliberately.
- Coverage is enforced at 100% on the combined multi-OS/multi-Python report (`coverage report --fail-under=100` in `coverage-combine`). Any new branch/line needs a test, including on rarely-hit OS-specific or Python-version-specific paths — several `docs_src/*_py310.py` files are `omit`ted from coverage entirely because they're syntax-gated example variants, not because they're untested.
- Tests require `PYTHONPATH=./docs_src` (`scripts/test.sh`) — running `pytest` directly without it will fail to import the tutorial example modules many tests exercise.
- `[tool.mypy]` runs in `strict` mode on `fastapi/` but relaxes rules for `docs_src.*` (`disallow_incomplete_defs`/`disallow_untyped_defs`/`disallow_untyped_calls = false`) since those are pedagogical snippets, not library code — don't assume docs examples reflect the type-checking bar for real changes.
- The `ty` type checker (`tool.ty.src.exclude` in `pyproject.toml`) excludes a long list of `docs_src/` paths that are "intentionally partial, dynamic, environment-driven, deprecated" — if you touch one of those tutorial files, `ty check` won't catch regressions there; rely on `mypy`/tests instead.
- Ruff ignores `B008` (function calls in argument defaults) repo-wide — this is intentional because `Depends(...)`/`Query(...)`/etc. are meant to be used as default argument values; don't "fix" these findings if you see them elsewhere.
- `fastapi/_compat/` is a compatibility seam, not general-purpose utility code — new Pydantic-version-sensitive logic belongs there (in `v2.py` or `shared.py`), not scattered inline in `routing.py`/`dependencies/utils.py`.
- The `test` CI matrix intentionally runs against both `starlette-pypi` (released) and `starlette-git` (`main` branch) — a PR can pass against the released Starlette version and still fail the `starlette-git` leg if it depends on Starlette internals that are about to change.

### Tone & standards — pick a delivery mode, keep the substance:

Keep the analysis rigorous and the bar high (staff/principal quality); the mode below changes only *how* findings are delivered.

**Default to Collaborative.** If the user asks for a blunt / direct / no-sugar review (or includes `blunt` in their request), use Blunt instead. The substance guardrail applies to both.

**Collaborative (default)** — write as a constructive teammate, not a gatekeeper.
- Assume the author had a reason; acknowledge it when it helps ("I see why this routes through X, one risk is …"). Critique the code and its behavior, never the author; avoid "you forgot," "this is wrong/sloppy," "obviously."
- Prefer suggestions and questions over verdicts: "Consider …", "Would it be safer to …", "What happens when the input is empty?"
- Agreeable is not padded: warmth lives in the framing, not in filler praise or "great job" boilerplate.

**Blunt (on request)** — direct and terse. Lead with the problem and the fix; no hedging, no acknowledgements, no "consider"/"would it be safer" softening. Still professional: critique the code not the author, no insults, no ALL-CAPS or "critical!" melodrama. Brevity over warmth.

**Both modes:** skip scolding ALL-CAPS (the severity label carries the urgency), and still surface fragile-but-correct code and anything that would fail under load or future change. Tone is never a reason to go quiet on a real problem.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

**Brevity must not dilute substance.** Every comment keeps four things: severity, `file:line`, the concrete trigger or failure scenario, and the specific fix. Everything else is cuttable, and most of it should go. Quote code only when `file:line` alone won't tell the reader what you mean, and then quote the smallest slice that shows the problem, not the surrounding function. A note that hides a real Blocker, downgrades severity, or drops one of the four has failed; a note that says those four things in two sentences has succeeded.

### Validate findings:

Before writing the final output, validate every finding you produced. For each one:

1. **Read the full file** referenced in the finding (not just the diff hunk).
2. **Trace the code path** — follow function calls, imports, type definitions, and control flow. Read caller and callee files as needed.
3. **Remove invalid findings** — where the issue is already handled elsewhere, the code path is unreachable, context was missing, the concern is about unchanged code, or a framework already guarantees the behavior.
4. **Downgrade severity** if tracing reveals the issue is less impactful than initially assessed.

A shorter, accurate review is far more valuable than a long review with false positives.

### End of review:

After validation, close with a short summary. No more than this:

**Verdict:** Approve / Request Changes / Block · reviewed at `<short-sha>`

Then one line naming the issues that drive that verdict (skip it entirely if there are none), and one line on test coverage — what's missing, or "covered" if nothing is. Don't restate findings the reader just read, and don't append a footer describing how the review was run.

Before writing, re-run the step 0 fetch and comparison. If the branch moved while you reviewed, read the new commits (`git diff <reviewed-sha>..origin/<branch>`), update any finding they fix or change, and stamp the new SHA. Then write this output to `REVIEW_OUTPUT.md`.

---

## Parallel Review

At 150 or more reviewable lines, read `.kimi-code/skills/fastapi-review/parallel.md` and follow it. It fans the review out to parallel lens sub-agents, validates their findings, and synthesizes the result. The comment format, rubric, and tone rules above still apply there.

---

## When NOT to use

- The user wants the diff *explained*, not critiqued — use the explain skill instead.
- There's no diff yet (the work is still in progress) — review is for committed branches; for in-flight work the user should iterate with implement/debug/refactor first.
- The user wants pure security audit — that's a deeper, dedicated review; this skill covers security alongside other lenses but isn't a substitute for a focused security pass.

