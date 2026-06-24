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
* **Comprehensive Testing:** Every code change requires corresponding test coverage. You must explicitly write test cases for:
  * **Happy Path:** Expected, successful execution flows.
  * **Error Paths:** Handled failures, invalid inputs, edge cases, and exceptions.
