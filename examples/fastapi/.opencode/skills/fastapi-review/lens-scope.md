# Lens: Scope & Conventions

## Look for: Scope, Project Conventions

### Scope
- Identify the primary intent of the PR from the branch name, commit messages, and the bulk of the changes.
- Flag any changes that do not appear related to that primary intent (e.g. drive-by refactors, unrelated formatting, feature creep).
- Use **Warn** severity for unrelated changes — they may be intentional, but should be called out for the author to confirm.
- Check that the PR does one thing well rather than bundling unrelated work.

### Project Conventions
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

If no repo-specific checks are listed above, read CLAUDE.md and any matching `.claude/rules/*.md` for the area being changed, and verify the PR adheres to the conventions and known pitfalls listed there.

## Additional rules

- Be precise about what is out of scope vs. in scope.
- For convention violations, reference the specific convention (file path or section in CLAUDE.md / `.claude/rules/`).
