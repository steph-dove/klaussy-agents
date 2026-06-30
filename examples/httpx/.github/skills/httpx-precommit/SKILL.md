---
name: httpx-precommit
description: Use when reviewing a staged diff or an about-to-commit/push change for last-mile issues — silent failures, leaked secrets, debug leftovers, blatant correctness landmines, and excessive/narrating comments. Reports findings on the changed lines only; it does not refactor or rewrite code. This is the canonical source for the Klaussy desktop pre-commit gate, which inlines the diff and adds its own machine-readable output contract.
disable-model-invocation: true
---

Apply exactly these five lenses to the CHANGED lines and their immediate context — nothing else. If no diff is inlined for you, read the staged change with `git diff --cached` first.

LENS 1 — Silent failures (your primary lens):
- Empty or swallowing catch blocks (caught errors not rethrown, surfaced, or meaningfully handled)
- Catch-and-continue where later code depends on the failed step
- Fallback values that mask failures (return null/[]/default on error with no signal to the caller or user)
- Success reported over partial failure (function returns ok / UI shows success when a sub-step failed)
- Errors logged where nobody looks (console/debug-level) when the user or caller needed to know
- Fire-and-forget promises / missing rejection handlers
- Optional chaining or defaults that convert real bugs into silent no-ops
- Killed/ignored exit codes, suppressed stderr

LENS 2 — Secrets & credentials (always Severity: High):
- API keys, tokens, passwords, private keys, connection strings with credentials, high-entropy literals that look like secrets — in ADDED lines. Placeholder values that are obviously fake (e.g. "YOUR_API_KEY", "xxx") are NOT findings.

LENS 3 — Debug leftovers (Severity: Low):
- Added print-debugging (console.log/print/dbg!) that is clearly scaffolding rather than intentional logging per this repo's conventions
- Newly commented-out blocks of code
- Added TODO/FIXME/HACK markers with no ticket reference

LENS 4 — Blatant correctness landmines (Severity: High ONLY — if you are not CERTAIN it is broken, do not report it):
- Unreachable code introduced by the change
- Conditions that are always true/false, inverted comparisons, assignment-in-condition
- Off-by-default boolean confusion (e.g. flag checked with the opposite sense of every other use in the file)

LENS 5 — Excessive comments (Severity: Low):
- Comments on ADDED lines that restate what the code plainly does ("// increment i", "// loop over the items", "// set x to 5"), narrate obvious steps, or just echo the function/variable name.
- Multi-line block comments where a single short line (or no comment) would carry the same information.
- Changelog / narration / "AI-tell" comments ("// Now we handle the case where…", "// This function will…", "// Added to fix the bug").
For each, the fix is: delete it (or condense to a short one-liner). Keep ONLY short comments that explain WHY — non-obvious intent, gotchas, links, or invariants. Do NOT flag: docstrings/JSDoc on public APIs, license/file headers, or genuinely clarifying "why" comments.

Explicitly NOT in scope: naming, formatting, performance, architecture, test coverage, lint-level nits, anything outside the diff. Do not suggest refactors. (Comment hygiene IS in scope — that is lens 5.)

Be precise and skeptical, but only report real issues — a deliberate, well-signposted degradation (comment explains it, user is notified elsewhere) is NOT a finding.

For each finding, give its severity, which lens caught it, the `file:line`, and the minimal fix in one or two lines. If there are no findings, say so plainly.
