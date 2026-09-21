# Lens: Correctness & Logic

## Look for: Correctness & Concurrency

### Correctness & Edge Cases
- Logic bugs, off-by-one errors, undefined behavior.
- Error handling gaps, partial failures.
- Incorrect return values or wrong types.
- Boundary conditions: empty inputs, nil/null, max values, overflow.
- State mutations that violate invariants.

### Concurrency & State
- Race conditions, shared mutable state.
- Thread safety, async misuse, ordering assumptions.
- Deadlocks, livelocks, starvation.
- Missing synchronization or incorrect lock scope.
- Assumptions about execution order in async code.

For each finding, be specific about the failure mode (the exact input or state that triggers the bug).
