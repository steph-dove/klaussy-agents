# Pre-Plan Guardrails

## 1. Scope & Execution Boundaries
* **Task Strictness:** Only implement what the user's task explicitly asks for. Do not over-engineer or solve unmentioned problems.
* **Smallest Necessary Change:** Always aim for the minimal amount of lines changed to safely fulfill the requirement. Do not perform unrelated refactoring.
* **Interactive Guidance:** If you identify optimizations or alternative architectural routes, offer them as guidance *only*. **DO NOT** implement or write code for them until the user explicitly responds and approves them.

## 2. Planning Mode Protocol
* **Review Phase:** When generating an Implementation Plan, explicitly layout the changes and immediately halt.
* **Wait for Consent:** Do not begin editing files, writing code, or calling execution tools until the user provides explicit written confirmation to proceed.

## 3. Code & Testing Standards
* **Repository Conventions:** Adhere strictly to the established patterns, syntax styles, file structures, and naming conventions already present in this repository.
* **Reuse before you write:** Before adding a function, helper, type, or constant, search the codebase for one that already does the job and use it. The plan should name the existing code it will reuse. Do not reinvent a utility the repo already has, and do not duplicate logic that belongs in one place.
* **Prefer built-ins and existing dependencies:** Reach for the language's standard library and the dependencies already in the project before hand-rolling an implementation (deep-clone, debounce, grouping, UUID, HTTP, parsing, config-loading) or pulling in a new package. A new third-party dependency is a decision to raise with the user, not a default.
* **One-line comments, and only where they earn it:** Keep comments to a single concise line that explains *why* — a non-obvious intent, a gotcha, an invariant, or a link. Do not add multi-line block comments, step-by-step narration, or comments that restate what the code plainly does. Prefer a clear name over a comment.
* **Comprehensive Testing:** Every code change requires corresponding test coverage. You must explicitly write test cases for:
  * **Happy Path:** Expected, successful execution flows.
  * **Error Paths:** Handled failures, invalid inputs, edge cases, and exceptions.
