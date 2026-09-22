# Lens: Architecture & Design

## Look for: Architecture, Design, Performance, Reliability, Dependencies

### Design & API Boundaries
- Leaky abstractions, tight coupling.
- Public interfaces that are hard to evolve.
- Violation of existing architectural patterns in the codebase.
- Responsibilities placed in the wrong layer or module.

### Performance & Scalability
- Inefficient loops, N+1 calls, blocking I/O.
- Work done in hot paths that doesn't need to be.
- Missing pagination, unbounded queries, or unbounded memory growth.
- Allocations or copies that could be avoided.

### Reliability
- Missing retries, timeouts, idempotency.
- Resource cleanup (connections, files, tasks).
- Failure modes that leave the system in an inconsistent state.
- Missing circuit breakers or backpressure for external calls.

### Dependency Changes
- If package manifest was modified: are new dependencies necessary? Are versions pinned?
- Flag any new dependencies that duplicate existing functionality.
- Evaluate transitive dependency impact.

### AI-pattern smells (reinvention, modularity, hidden dependencies)
- **Reinvented stdlib or built-ins**: manual deep-clone / debounce / throttle / slugify / date arithmetic / array partitioning when the language has built-ins (`structuredClone`, `crypto.randomUUID`, `Array.prototype.flat`/`flatMap`, `Intl.*`, `Object.groupBy`, Python's `itertools.*` / `functools.*` / `collections.Counter`, Go's `slices`/`maps` packages, etc.).
- **Bespoke utilities** (manual `groupBy`, `partition`, `uniqBy`, `pick`, `mapValues`, `chunk`) when the codebase already imports lodash/Ramda/`itertools`/similar — duplicates with subtly different semantics that drift over time.
- **Monolithic files** (>500 lines with multiple unrelated responsibilities) or **god classes** (>15 methods spanning mixed concerns). Different scale from "long function" — flag the missing module/class boundary.
- **Local / inside-function imports** (`from X import Y` inside a function in Python, `require('X')` inside a function in Node) outside the legitimate circular-import-breaking case. Hides the dependency surface, prevents IDE/linter analysis, and signals the author didn't want to commit to a real top-level dependency.
- **Hand-rolled HTTP / parsing / config-loading** when the project already uses a client library (axios/requests/httpx) or framework helper. Different from "wrote it from scratch in a new project".

## Additional rules

- Think about how changes behave at scale and over time, not just on the current request.
