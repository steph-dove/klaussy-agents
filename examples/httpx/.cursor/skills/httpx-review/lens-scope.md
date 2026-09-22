# Lens: Scope & Conventions

## Look for: Scope, Project Conventions

### Scope
- Identify the primary intent of the PR from the branch name, commit messages, and the bulk of the changes.
- Flag any changes that do not appear related to that primary intent (e.g. drive-by refactors, unrelated formatting, feature creep).
- Use **Warn** severity for unrelated changes — they may be intentional, but should be called out for the author to confirm.
- Check that the PR does one thing well rather than bundling unrelated work.

### Project Conventions
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

If no repo-specific checks are listed above, read CLAUDE.md and any matching `.claude/rules/*.md` for the area being changed, and verify the PR adheres to the conventions and known pitfalls listed there.

## Additional rules

- Be precise about what is out of scope vs. in scope.
- For convention violations, reference the specific convention (file path or section in CLAUDE.md / `.claude/rules/`).
