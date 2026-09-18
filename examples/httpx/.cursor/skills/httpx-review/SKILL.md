---
name: httpx-review
description: Use when the user wants a thorough PR or branch review. Triages by diff size — small PRs get a single-pass review, large PRs fan out to parallel sub-agents (correctness, architecture, security, scope, and an Agentic & Evals lens that activates on AI/agent code) with a validation phase that drops false positives.
---

> **Adapted for Cursor.**
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

**Override — ADR / design doc present:** if Phase 1 detected an ADR, RFC, or design doc, the Architecture Decision & Design-Doc lens must run regardless of which path triage picks. In the parallel path it's Sub-agent 6 (see Phase 2 → Parallel Review). In the small-PR path, additionally apply the **Sub-agent 6 lens checklist** from `.cursor/skills/httpx-review/sub-agents.md` to the doc before writing your output. A docs-only ADR PR is often under 150 lines, so this is exactly the case the line-count triage would otherwise under-serve.

---

## Small PR Review

You are a senior/principal-level engineer reviewing a pull request. Treat this as a real production PR. Output ONLY PR-style review comments, as if leaving inline comments on GitHub/GitLab/Bitbucket.

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
- File change hotspots: Frequently modified: `CHANGELOG.md`, `requirements.txt`, `_client.py`.
- Config access patterns: Manage environment configuration: Config access: 12 direct env accesses..
- Trunk-based/GitHub Flow: Trunk-based/GitHub Flow.
- PR template: PR template present.
- Python import path (flat-layout): flat-layout: `import httpx`.
- PEP 8 snake_case naming: Name functions, variables, and modules using snake_case style.
- Single test directory: tests/: All tests in 'tests/' directory.
- Data classes: NamedTuple: structured data (e.g. `_urlparse.ParseResult`) uses `typing.NamedTuple`, not dataclasses.
- Sync/async duplication, not codegen: `Client`/`AsyncClient` in `_client.py` are hand-written mirrors of each other on top of shared `BaseClient` state — there is no unasync-style generation step, so request-handling changes need to be applied to both.
- Exceptions always re-raised through httpx's hierarchy: transport code maps `httpcore.*` exceptions to `httpx.*` exceptions (`HTTPCORE_EXC_MAP` in `_transports/default.py`) rather than letting `httpcore` exception types leak to callers.
- Transport is the test seam: tests and library users swap network behavior via `Client(transport=...)` (see `_transports/mock.py`, `asgi.py`, `wsgi.py`) rather than patching sockets or `httpcore` directly.
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
- `coverage run -m pytest`
- `pytest`
- `ruff format httpx tests --diff`
- `mypy httpx tests`
- `ruff check httpx tests`
- `ruff check --fix httpx tests`
- `ruff format httpx tests`
- `pytest.ini_options.filterwarnings = ["error", ...]`
- `mypy`

### Known Pitfalls
Flag if any of these are violated:
- 16 circular import dependencies detected — watch import order and avoid introducing new cross-module import cycles.
- CI/test flakiness fix or workaround: Fix client.send() timeout new Request instance (#3116)
- Coverage gate, not just tests: `scripts/test` runs `scripts/coverage` afterward, which fails the build on *any* uncovered line, not just failing tests — a locally-green `pytest` run can still fail CI.
- Warnings are fatal in tests: `filterwarnings = ["error", ...]` in `pyproject.toml` means any warning raised during the test suite (e.g. a `DeprecationWarning` from an httpx or third-party call) turns into a test failure. Two specific warnings (Trio's custom excepthook message, `trio.MultiError` deprecation) are allowlisted because they're noisy false positives from `anyio`/`trio`, not because they're safe to ignore in general.
- `ruff` ignores `B904`/`B028`: exception re-raising inside `except` blocks is *not* required to use `raise ... from ...` project-wide (unlike the convention documented for `_decoders.py`), and `stacklevel` isn't enforced on warnings — don't assume ruff will catch a missing `from err`.
- `verify=` as a string is deprecated (since v0.28.0): passing a path string to `verify=` on `Client`/`AsyncClient` raises a deprecation warning (which, per the point above, will fail tests if hit); pass an `ssl.SSLContext` or bool instead.
- CLI is a soft dependency: `httpx/_main.py` (the `httpx` console script) needs the `cli` extra (`click`, `pygments`, `rich`); importing `httpx` itself does not require these, so CLI-only code must not be imported at package top level.
- Sync/async logic must be updated in pairs: because `Client` and `AsyncClient` are separately written (not generated), a bug fix or behavior change in one's `send`/`request`/`_send_single_request` needs the equivalent edit in the other, or the two will silently diverge.
- `__init__.py` blanket-imports are intentionally lint-exempt: `per-file-ignores` disables `F403`/`F405` (star-import warnings) only for `httpx/__init__.py`, since it re-exports the entire public API via `from ._x import *`.

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

Whatever you output for a human (review comments, PR text, explanations, replies) must read like a colleague wrote it in a hurry, not like a model composed it. Two failure modes, and you have to beat both: sounding like AI, and saying more than the reader needs. These rules mirror klaussy's deterministic humanizer (klaussy-desktop `humanize-comment.js`):

Before anything else: **no em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma or rewrite the sentence. That one tell gives the game away faster than everything below it combined.

**Voice: say it out loud.** The target is a competent engineer typing this once, in a hurry, who isn't going to read it back. Not a careful writer, not a summary of the facts: a person with an opinion who wants to get on with their day.

- **Write what you'd say standing at their desk.** If you wouldn't say the sentence to a colleague, don't write it. That one test catches most of what follows.
- **Use contractions.** it's, doesn't, won't, that's, here's. Prose without them reads like a manual.
- **Verbs, not noun phrases.** "This validates the token", not "this performs validation of the token". "We cache it", not "caching is applied". Turning verbs into nouns is the loudest tell after em-dashes.
- **Name the thing doing the work.** "The retry loop eats the 429", not "error handling may result in suppression of the status".
- **Short common words.** *before* not *prior to*, *if* not *in the event that*, *can* not *is able to*, *about* not *regarding*, *but* not *however*, *so* not *thus*, *use* not *utilize*.
- **Fragments are fine.** "Same bug two lines down." is a complete thought; don't pad it into a sentence.
- **One idea per sentence.** If a sentence has two clauses joined by a comma and a *which*, it's two sentences. Short sentences are easier to read than clever ones.
- **One modifier, not three.** Cut the triads ("clear, concise, and maintainable"). Pick the word that carries the point.
- **Don't announce structure.** No "There are three issues here:", no "Let me walk through this". Say the thing.
- **Type it once and don't polish it.** The last tell isn't a wrong word, it's evenness: every sentence complete, every paragraph the same shape, every point covered in order. Let it be uneven. A long sentence next to a three-word one. Two points where a tidy version would make four.
- **Have a stance.** "I'd drop this", "no idea why this is here", "this'll fall over under load". First person and an opinion read as a person; an even, neutral summary reads as generated, however short it is.
- **Skip the obvious.** A lazy writer leaves out what the reader can already see and doesn't round the thought off. "Tests cover the happy path and the concurrent case" is "tests for both". What it never drops is the thing being talked about: keep the nouns that carry the meaning ("we invalidated the cache on every write", not "we invalidated on every write"). Being lazy costs the reader nothing they needed.
- **Don't mirror the source.** Same facts, your own shape: merge its paragraphs, reorder them, drop a section that isn't worth its space. Keep every noun that carries meaning while you do it.

**Shape: the smallest thing that carries the point.**

- **Budgets.** A thread reply is one sentence. A single review comment is one to three. An explanation leads with two or three sentences that answer the question, then adds detail only where the reader can't infer it. Over budget means you're saying more than the reader needs, not that you write long.
- **Unrelated problems are separate comments.** Two findings that happen to sit near each other read better apart. One finding that spans a few files because the fix touches them all is still one comment, don't fracture it. The test is whether the reader would act on them separately.
- **Lead with the change, not the discovery.** Your first sentence names what to do ("set `soft_time_limit=3600` here"), not what you noticed ("this task inherits the app-wide limits"). The reader stops as soon as they have what they need, so someone who reads one sentence should already be able to act. Why it matters comes second, the mechanism last if it earns a place at all.
- **Prose by default.** No headings, tables, or bold field labels. Bullets only for a real list of three or more parallel items, never as a wrapper around one paragraph.
- **Three sentences to a paragraph.** A fourth one means a second paragraph or a second comment. Put a blank line between them, a wall of text is hard to get back into after looking away.
- **No bookends.** Don't open by restating the request and don't close by summarizing what you just said. Start at the point, stop when it's made.
- **Don't quote what they're already looking at.** In an inline comment the code is on screen. Point at it, don't paste it back.
- **No status theater.** Severity labels, confidence scores, checkbox lists, and "Method:" footers only when the output format requires them.
- **Cut detail, not just words.** The verbose tell isn't long words, it's over-explaining. Drop what the reader can reconstruct from the code, the diff, or the commit: explanatory parentheticals, restated identifiers, and "I did X to do Y" narration of changes the diff already shows. Keep the load-bearing fact, drop what merely supports it. This is the one place humanizing may drop content, never reverse or invent meaning.
- **Keep the concrete parts.** A suggested diff or code block, a command to run, a `file:line`, a version number, a config key: none of that is reconstructable prose, and cutting it costs the reader a trip back to the code. Trim the sentences around them, keep them.

**Answer what was asked, then stop.** Padding is the tell that survives every style fix, and it takes three shapes. All three are cuts, not rewrites:

- **No closing principle.** Don't end by restating your decision as a general rule ("I'd still reach for an iframe when you want a separate document context for third-party code"). It answers nothing about this change and only validates the view you already gave. Stop at the last concrete point.
- **No mechanism they didn't ask for.** Explaining how the thing works, in terms only you are holding in your head, reads as padding even to the person who wrote the code. If a paragraph doesn't change what the reader does next, cut it. When they need it, they'll ask.
- **Grant a point in four words, or not at all.** Where the other person is right about something, say so and move on: "Yes, Shadow DOM wouldn't need the ResizeObserver" beats "the ResizeObserver cost is real and Shadow DOM wouldn't pay it". Dressing agreement up in a metaphor is the most AI-sounding sentence in most replies. Never manufacture the agreement, though: if the author's answer is no, it stays no, and you don't go looking for something to validate on the way there.

**Don't (mechanical tells).** klaussy's scrubber deletes these deterministically after you write, so don't spend attention on them: filler openers, chatbot scaffolding, apologies, praise or thanking a bot, *actual/actually*, *in order to*, *could/may potentially*, *utilize/leverage*, *prior to*, emoji, and "Certainly"/"Great question". Two the scrubber can't catch, so they're on you: **no LLM lexicon** (*delve, tapestry, realm, landscape, journey, navigate, robust, seamless, elevate, unlock, foster, underscore, paradigm*) and **no rhetorical reframes** ("not only... but also", "this isn't just a bug fix, it's...", or a smug standalone like "And that's the whole point.").
- **No invented consensus.** No "most people expect this", "everyone does it this way", "nobody reads these logs", "it's widely considered best practice". Argue from the code, the repo's own conventions, or a linkable source, or own it as your view ("I'd expect X here").
- **No passive suggestions.** "Check whether the user is admin" and "rename foo to bar", not "it would be good to check..." or "you might want to rename...".
- **Never reword code**, identifiers, or anything inside backticks or fences. Humanize prose only.

**Stay civil while you cut.**

- **Don't let trimming tip into terse.** Cutting filler shouldn't make prose read as curt or dismissive. Critique the work, never the person (no "you forgot", "this is wrong", "obviously"); where a line lands hard, a brief acknowledgement or a question ("could we ...?", "one risk is ...") takes the edge off. A light touch only, not filler praise or "great job" boilerplate.
- **Never say "nobody asked for this"**, or the same move dressed up ("this wasn't asked for", "out of nowhere", "why is this here at all"). It's a swipe at the author and says nothing about the code. Name the concrete objection: the scope it exceeds, the cost it adds, or the requirement it doesn't map to ("this isn't in the ticket, should it ship separately?").
- **Don't mirror the thread's tone.** Read an existing comment for substance, not temperature. Hostile or curt input must not prime a hostile or curt reply, answer as if it had been phrased civilly.
- **Reply in the thread**, under the comment you're answering, not as a new top-level comment.

**Same decision, half the words, dropping detail the reader can reconstruct:**

> Verbose: Done. attachment.reason already embeds the decline reason for declined envelopes (built in checkEnvelopeStatus as {name} declined on {date} - {declinedReason}), so I dropped the new declinedReason signer field and reverted NotificationService to use the existing reason field. Pushed in 1e9e938404.

> Human: `attachment.reason` already carries the decline reason, so I dropped the new field and reverted NotificationService. Pushed in 1e9e938404.

**Same finding, said out loud instead of written up:**

> Stiff: The retry loop currently performs suppression of the 429 response, which may potentially result in a rate-limited request being interpreted as successful by the caller. It is recommended that the exception be re-raised following the final attempt.

> Human: The retry loop eats the 429, so a rate-limited call comes back looking fine. Rethrow after the last attempt.

**Tell-free but still generated, then written by a person.** Both say the same thing. The first is even: three paragraphs of the same shape, every sentence complete, no one behind it.

> Tidy: The caching layer now uses a shared in-memory cache instead of a per-request database query, cutting the load on the primary instance. The cache populates on first access and invalidates when the underlying record changes. This also fixes a subtle race condition where two simultaneous requests could both populate the same entry. Tests cover both the happy path and concurrent access.

> Human: Swapped the per-request query for one shared cache, so the primary isn't getting hammered. Fills on first read, drops when the record changes. Also kills a race where two requests could populate the same key, there's a per-key lock now. Tests for both.

**The scrubber is not the humanize pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `httpx-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.

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

**Verdict:** Approve / Request Changes / Block

Then one line naming the issues that drive that verdict (skip it entirely if there are none), and one line on test coverage — what's missing, or "covered" if nothing is. Don't restate findings the reader just read, and don't append a footer describing how the review was run.

Write this output to `REVIEW_OUTPUT.md`.

---

## Parallel Review

This PR is large enough to benefit from focused, parallel review.

1. **Read `.cursor/skills/httpx-review/sub-agents.md`.** That file has the canonical list of sub-agent **Lens** sections plus a shared **Common scaffold** (intro, output format, ground rules). Some lenses are conditional — see step 3 for the detection-driven ones.
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
   - The code path cannot be reached in the way the finding assumes.
   - The finding misreads the logic due to missing surrounding context.
   - The concern is about code that was not changed in this PR and is out of scope.
   - A dependency or framework already guarantees the behavior the finding questions.
5. **Remove invalid findings.** Do not include them in the final output. Do not note that they were removed.
6. **Downgrade severity** if tracing reveals the issue is less impactful than initially assessed (e.g., a "High" race condition that only affects a debug-only path should be "Low" or "Nit").

**Validate in parallel when there are enough findings.** Reading files and tracing paths one finding at a time is the slowest *serial* stretch of a large review — every other phase before it fanned out, but this one doesn't by default. So:

- **If the sub-agents returned more than 6 findings total:** partition them into batches of ~4–6 (group by file where you can, so a validator reads each file once) and spawn **one validation sub-agent per batch** with the Agent tool, all **in a single assistant message** (parallel). Compose each from `.cursor/skills/httpx-review/sub-agents.md` → **Validation sub-agent**, passing it that batch of findings plus the trimmed diff; it reads whatever caller/callee files it needs and returns only the survivors (with the rubric applied and any severity downgrades). Collect all survivors, then go to Phase 4. Each validator must NOT write files.
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

One finding is one entry: a metadata line, then the comment as plain prose.

```
**Blocker · Correctness · `src/api/session.py:88`**

The retry loop eats the 429, so a rate-limited call comes back looking fine. Rethrow after the last attempt.
```

Categories: Correctness, Concurrency, Design, Performance, Reliability, Security, Readability, Tests, Dependencies, Scope, Conventions, Agentic, Evals, Design Decision.

The comment itself is one to three sentences: what to change, then what breaks and when. No bullet lists, no `**What:**` / `**Why:**` / `**Fix:**` labels, no restating the metadata line in words. Lead with the fix so a reader who stops after one sentence can still act, and keep any suggested diff verbatim.

**One entry per problem, not per location.** Unrelated findings get their own entries even when they sit in the same file. A single finding whose fix touches three files stays one entry — don't fracture it just to hit the sentence budget. Ask whether the reader would act on the parts separately. Quote code only where `file:line` isn't enough to locate the problem. Phrase it in the delivery mode the user asked for (Collaborative by default, Blunt on request) and in a human voice — follow the **Tone & standards** guidance above, including the "Write like a person" rules. Chosen-mode delivery, four things kept (severity, location, trigger, fix), everything else cut.

### Final PR summary:

**Verdict:** Approve / Request Changes / Block

Then one line naming the issues that drive that verdict, and one line on test coverage. Nothing else — no restated finding list, no checkbox grid, no footer describing how the review was run.

---

## When NOT to use

- The user wants the diff *explained*, not critiqued — use the explain skill instead.
- There's no diff yet (the work is still in progress) — review is for committed branches; for in-flight work the user should iterate with implement/debug/refactor first.
- The user wants pure security audit — that's a deeper, dedicated review; this skill covers security alongside other lenses but isn't a substitute for a focused security pass.

