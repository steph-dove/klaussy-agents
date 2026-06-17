---
name: {{REPO}}-test
description: Use when the user wants tests written for current changes (uncommitted diff or recent feature). Matches the repo's existing test framework, fixtures, and assertion style. Covers happy path, edge cases, and error paths without over-mocking.
allowed-tools: Read Grep Glob Bash Edit Write
---

Write tests for the current changes. Follow these steps:

1. **Read CLAUDE.md** to understand the project's test framework, conventions, and test commands.
2. **Read any `.claude/rules/*.md`** whose `paths:` glob matches the changed files — they capture testing conventions specific to this layer (e.g. how API tests are structured vs. how DB tests are structured).
3. **Check `git diff`** to identify what changed. Classify the change:
   - **Pure refactor** (code moved/renamed, no behavior change): update existing tests' imports and call sites; do NOT invent new tests for behavior that already had coverage.
   - **New behavior or modified behavior**: continue to step 4.
4. **Find existing test files** for the modules you're testing. Read them fully — match their patterns:
   - File naming and location conventions.
   - Fixtures, factories, helpers, and setup/teardown patterns.
   - Assertion style and test structure.
   - How similar features are tested (use as a template).
5. **Write focused tests** that cover:
   - **Happy path** — the expected behavior works correctly.
   - **Edge cases** — empty inputs, boundary values, null/nil, large inputs.
   - **Error cases** — invalid input, missing data, permission failures. Test that errors are handled, not just that they don't crash.
   - **Behavior, not implementation** — test what the code does, not how it does it. Tests should survive a refactor that preserves behavior.
6. **Run the test suite** to verify everything passes, including your new tests.

## Rules

- **Match existing patterns.** If the codebase uses factories, use factories. If it uses fixtures, use fixtures. Don't introduce a new testing pattern.
- **Mock only**: (1) external network services (HTTP APIs, payment gateways, third-party SDKs), (2) slow I/O without a fast fixture (real databases, filesystems), (3) non-deterministic sources (current time, randomness). Do NOT mock the code under test. Do NOT mock internal modules just to avoid setting them up.
- **Don't under-test.** If you changed a conditional, test both branches. If you added error handling, test the error path. "Happy path only" is not adequate coverage.
- **Each test should test one thing.** If a test name needs "and" in it, split it into two tests.
- **Tests must be deterministic.** No reliance on timing, ordering, or random data without seeds.

## When NOT to use

- The diff has no behavior change at all (formatting, comments, dead-code removal) — there's nothing to test.
- The user wants the test suite *fixed* (failing tests) rather than new tests written — diagnose the failures with debug or fix instead.
- The user wants to rewrite all existing tests to a new framework — that's a refactor of test infrastructure, not test authoring.
