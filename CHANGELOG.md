# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Releases
before 0.6.0 are recorded in the git tags (`v0.2.0`–`v0.5.1`).

## [0.18.0] - 2026-07-16

### Added

- **The commit guard blocks function-local imports.** Agents write an import
  where the need surfaces rather than where it belongs — `import json` three
  frames deep, because that's the line they were on. Ruff's `PLC0415` is the same
  rule but judges a whole file, which would turn every pre-existing local import
  into a landmine (90 in this repo alone), and a noisy guard gets disabled. The
  new `klaussy import-lint` scopes to the lines in flight, so it only asks about
  an import the commit actually adds. Verified against ruff across `src/` and
  `tests/`: 90 findings each, no disagreement in either direction. Block-only,
  with `# noqa` on the line honored — a local import is sometimes the only way to
  break a cycle or defer an optional dependency, and no AST walk can tell that
  from habit. Module-level `if TYPE_CHECKING:` and `try/except ImportError` are
  top-level scope and never flagged. The `self-review` checklist asks for the
  same thing, so the model hoists before the gate fires.

### Fixed

- **The read-injection guard no longer blocks a repo's own test code.** A suite
  that tests injection handling has to contain injection strings, so the guard
  read its fixtures as live injections and refused the file — klaussy's own
  `tests/test_cli.py` was unreadable to any agent working in a scaffolded repo.
  Test *source* is now exempt, scoped three ways so the guard keeps its teeth:
  source extensions only (a data blob under `tests/` is still scanned), file
  reads only (a fetch is never waved through on the strength of a path), and test
  layout conventions only (`tests/`, `__tests__/`, `test_x.py`, `x_test.go`,
  `x.spec.ts`, `conftest.py`). Both the Claude and cross-agent copies are fixed.

### Documentation

- **The `grant-permissions` skill has a table entry.** It was the headline of
  0.16.0 but appeared only as a bare name in the "also bundles" list.
- **Corrected the commit-guard scoping claim.** "Every check is diff-scoped" was
  wrong: secrets, comments and imports narrow to the changed lines, but the
  project's own format and lint judge the whole staged file.

## [0.17.1] - 2026-07-16

### Fixed

- **The dependency gate no longer blocks a manifest sync in a pipeline.** The
  guard found `pip install` and then read every token to end-of-line as a package
  name, straight through `;`, `&&`, and `|` — so `pip install -e . 2>&1 | tail -1`
  blocked, reporting `2>&1, |, tail, echo` as the dependency it had found. The
  `pip install -e .` exemption was real but only survived a bare command line.
  A line is now split on shell operators and each command judged on its own.
  Scanning a segment stops at a redirect, since package names always precede one,
  and a bare file-descriptor number is skipped (`2>&1` tokenizes as `2`, `>&`,
  `1`). Parsing moved to `shlex.shlex(punctuation_chars=True)`, since
  `shlex.split` leaves an operator glued to its neighbour (`requests;` stays one
  token) and hides the boundary the split needs. A compound line with two
  installs now reports both packages.

## [0.17.0] - 2026-07-16

### Added

- **Comment lint blocks past two sentences.** The run-length and word-count
  heuristics only caught the long tail, so a three-sentence narration comment on
  two lines sailed through. Sentences are counted across a wrapped comment, since
  consecutive lines are one logical comment. Two is deliberate rather than one: a
  one-sentence cap flags 45% of `src/klaussy`'s own comment blocks, including
  load-bearing why-comments, which would make `--no-verify` a habit. Block-only
  like the rest of the check — which sentence is worth keeping is a judgment call,
  so the author makes it, not a regex. Counting errs low (a break needs terminal
  punctuation, whitespace, and a capital), so `hooks.py`, `0.16.0`, trailing URLs,
  and `e.g. Claude` don't split a sentence.
- **The stop-hook self-review leads with comments.** Comment removal was one
  clause buried mid-checklist; it's now the first step, biased toward deletion —
  cut what narrates or restates the code, keep only what the code cannot say, hold
  survivors to a single sentence. The model is asked for one sentence while the
  lint blocks at three: it can judge which sentence earns its place, so it aims
  tighter than the deterministic backstop can safely enforce. The `self-review`
  skill checklist is kept in sync.

### Fixed

- **Hook upgrades no longer duplicate entries.** `_merge_managed_hooks` keyed on
  the exact command string, but the command form has changed across releases (a
  bare relative path, then `python3 ${CLAUDE_PROJECT_DIR}/…`, now the
  `klaussy-hook` launcher), so an old entry never matched the new desired one and
  every upgrade appended a copy while leaving the stale one behind. The stale
  copies weren't just noise: a bare relative path resolves against the session
  cwd, so any session not rooted at the repo (a subagent, a worktree) failed to
  find the guard and blocked every matching tool call. Entries are now keyed on
  the guard script name, so an upgrade rewrites in place and leaves the user's own
  hooks untouched. Repos carrying duplicates from an earlier version are repaired
  by this release's version-gated re-run.

## [0.16.0] - 2026-07-15

### Added

- **`grant-permissions` skill.** Grants the typical dev permissions needed to
  work in a repo so routine commands stop prompting, while keeping secret files
  denied. Detects the stack (including `scripts/` and Makefile runners that a
  bare `Bash(pytest *)` rule misses) and the app's run command, allows shell
  builtins so compound `cd x && <cmd>` lines don't prompt, and documents an
  honest boundary: curated mode trusts the agent to run repo code, and per-tool
  denies don't stop Bash reads of secret files. Broad mode is opt-in.
- **Per-agent permission scoping.** The skill is scoped to each agent's own
  permission surface via a new `{{PERMISSIONS_TARGET}}` sentinel: `CapabilityProfile`
  carries `permissions_file`/`permission_syntax`, `render.py` resolves it per
  profile, and the Claude scaffold path feeds Claude's own file through the same
  composer. Agents without a committed allow-list (Cline) render a "doesn't
  apply" note; Aider has no profile so it never renders the skill.

## [0.15.2] - 2026-07-14

### Fixed

- **`rest-of-the-owl` now treats QA as a blocking gate.** Phase 4 (QA) already
  ran before the PR, but it was framed purely as evidence-gathering, so a change
  QA had shown to be broken could still advance to a PR and get caught later by
  CI or a reviewer. QA is now an explicit gate: a broken screenshot, wrong
  endpoint response, CLI error, or failing test sends the run back to fix and
  re-QA before the PR is opened.
- **`plan` and `implement` block on design assets they can't see** instead of
  inventing them. When a ticket references a mockup, screenshot, Figma link, or
  attached image the agent has no tool to retrieve (`gh issue view` shows issue
  text but not image attachments), the skills now hard-block and ask the user to
  provide it rather than fabricating UI text, layout, spacing, or copy.

## [0.15.1] - 2026-07-14

### Fixed

- **Resolve bot-thanking and superlative AI tells in humanizer.** Prevented automated PR comment reviews from thanking bots (e.g. `@dependabot`, `@codecov-bot`, `@github-actions`) and using superlative compliments like *"this is the sharpest catch in the review"*.
- **Extend tells coverage**. Added emojis, transition word openers, apologies, and utilize/leverage replacements to the deterministic Python scrubber.

## [0.15.0] - 2026-07-13

### Added

- **`klaussy-hook` launcher for OS-agnostic hooks.** A committed hook command
  can't portably name a Python interpreter (`python3` is absent on stock Windows;
  `python` isn't guaranteed on Linux/macOS), and Claude/Gemini hook configs have
  no per-OS field — so the interpreter was frozen to whatever machine ran
  `klaussy init`. The new `klaussy-hook` console script — installed on `PATH` by
  pip on every OS (`klaussy-hook.exe` on Windows) — runs the guard under klaussy's
  own interpreter, so the committed command names no interpreter and just works on
  any OS with nothing for the user to adjust. Claude and Gemini hooks invoke it;
  Codex gains a per-OS `command`/`commandWindows` (`py -3`) override;
  Copilot/OpenCode keep their existing OS-agnostic mechanisms. See the README
  "Cross-Platform Support" matrix (Cline hooks remain macOS/Linux-only by spec;
  Cursor and Antigravity Windows execution is undocumented).
- **`<repo>-qa` skill** — captures PR-ready QA evidence sized to the change:
  screenshots for UI, exercised endpoints and e2e for backend, command output
  for a CLI, tests for a library. Artifacts land in a `Downloads/<repo>-<branch>`
  folder the user can open.
- **`<repo>-rest-of-the-owl` skill** — runs the full development loop from a task
  definition (plan → implement → review → QA → humanized PR → poll CI and code
  review, fixing and resolving) and stops at the merge button.

### Fixed

- **Cross-platform (macOS / Linux / Windows) hardening of hooks and skills.**
  Guard scripts now read stdin as UTF-8 instead of the process locale encoding,
  so a Windows `cp1252` locale no longer fail-opens on em-dashes/smart quotes
  (the very input the comment guard exists to catch). The commit guard resolves
  tools via `shutil.which` (honoring Windows `PATHEXT`) and runs `.cmd`/`.bat`
  shims through `cmd.exe`, so `npm`/`eslint`/`prettier` gating works on Windows
  instead of silently passing. The `new-worktree` and `humanize` skills no longer
  instruct the agent to run POSIX-only shell idioms verbatim.
- **Duplicate `# Rules for` header in nested conventions.** The generated
  `.claude/rules/*.md` bodies open with their own `# Rules for <glob>` heading,
  which the non-Claude backends re-wrapped with a second one — producing a visible
  duplicate in nested `AGENTS.md`/`GEMINI.md` and a redundant header in inline
  rule files. The heading is now stripped once at load; Claude still copies the
  raw rules files untouched.

## [0.14.0] - 2026-07-13

### Added

- **`<repo>-run` skill** — launches and drives the project's app so you can watch
  a change work end-to-end instead of trusting tests alone. It reads the run
  command from `CLAUDE.md`'s **Commands** section (falling back to stack defaults
  for Python/Node/Go/Rust when none is named), backgrounds long-running servers
  and waits for their ready signal before driving them, then reports the actual
  output. It refuses to patch code to make the app start — a broken app is a bug
  for the debug skill, not something to work around here.
- **`<repo>-self-review` skill + `self_review_guard.py` hook** — a last-pass
  review of your own uncommitted diff against a fixed checklist (reuse, stdlib,
  comments, dead code, tests, scope) before declaring an implementation done,
  with a companion guard that nudges the agent to run it.
- **Additional bundled skills** — `address-review`, `deps`, `document`, and
  `release`, joining the canonical `SKILL_NAMES` list.

### Changed

- **Pre-plan guidance and commit guard refinements** — updated plan-step
  guardrails and commit-guard behavior; example scaffolds regenerated across all
  supported agents.

## [0.13.0] - 2026-07-01

### Added

- **OpenCode backend** — klaussy's ninth supported agent. Project-wide
  conventions land in a root `AGENTS.md`; path-scoped rules become modular
  `.opencode/rules/*.md` files wired in via the `instructions` glob in a root
  `opencode.json` (OpenCode has no nested-rule auto-discovery). Skills use the
  standard `SKILL.md` spec under `.opencode/skills/`. `opencode.json` also
  carries last-match-wins `permission` read/bash rules — the broad default first,
  specific allow/deny after — with `read` denies covering the sensitive
  patterns. Because OpenCode's hook mechanism is an in-process Bun plugin rather
  than a shell command, a committed `.opencode/plugins/klaussy.js` bridges tool
  hooks to the shared Python guards under `.opencode/hooks/`.
- **OpenCode pre-plan guardrails** — OpenCode has no context-injection hook
  event, so (as with Antigravity's `.antigravityrules`) klaussy's pre-plan
  guidance rides an always-loaded `.opencode/rules/klaussy-pre-plan-guidance.md`
  instructions file instead of a hook, bringing OpenCode's guardrail coverage to
  Claude parity.
- **OpenCode-aware subagent/plan-mode skill banners** — `CapabilityProfile`
  gained optional `subagent_mechanism` / `plan_mechanism` fields. OpenCode sets
  them so skills that fan out (e.g. `review`) get an affirmative banner naming
  OpenCode's real parallel subagents (`@`-mention `@general`/`@explore`/`@scout`)
  and its Plan agent, instead of the generic "use your equivalent, else go
  sequential" note the other non-Claude backends receive.

## [0.12.2] - 2026-06-30

### Fixed

- **Commit guard honors `git commit --no-verify`** — `--no-verify` (and the `-n`
  short form, including combined clusters like `-an`/`-nm`) now bypasses the
  guard entirely: it runs no checks and emits no output. Previously the guard
  intercepted every `git commit` regardless, so an explicit hook opt-out was
  ignored and the guard's output could flood an agent's context. Applies to both
  the Claude and cross-agent guard templates.
- **Commit guard output is terse** — the guard no longer echoes each resolved
  command (with its full staged-file list) before running it, nor prints a
  per-tool "could not run" line when a checker isn't installed; a missing tool
  now allows the commit silently. On a real failure it prints a single line that
  points at the failing tool's own output and at `--no-verify`, instead of
  repeating the whole command and path list. This keeps a blocked commit from
  flooding an agent's context.
- **Commit guard runs each formatter/linter only on the file types it
  understands** — the guard previously passed every staged path to `ruff`, so a
  `.md`/`.json`/`.toml` committed alongside Python made ruff fail to parse it and
  wrongly block the commit. Each command's `__KLAUSSY_PATHS__` is now scoped to
  the staged files matching its tool (ruff → `.py`/`.pyi`, eslint → JS/TS, …);
  when nothing staged is applicable the command is skipped entirely. Tools that
  already self-filter (`prettier --ignore-unknown`, `klaussy comment-lint`) are
  unaffected. Both the Claude and cross-agent guard templates are fixed.

Because hook scaffolding is version-gated on `.klaussy-version`, existing
installs pick up both fixes on a re-run after the version bump (or with
`--force`).

## [0.12.1] - 2026-06-29

### Fixed

- **Verbose-comment precommit check only scans the diff** — `klaussy
  comment-lint` gained a `--diff` flag (now used by the commit guards) that
  scopes findings to lines changed vs `HEAD`. Previously the check read each
  changed file in full, so a long pre-existing comment block anywhere in a
  touched file blocked the commit even when the diff never went near it.
  New/untracked files are still scanned in full. Because hook scaffolding is
  version-gated on `.klaussy-version`, existing installs pick this up on a
  re-run after the version bump (or with `--force`).

## [0.12.0] - 2026-06-29

### Fixed

- **Hook scripts resolve from the project root across all agents** — installed
  guard hooks now locate their scripts relative to the project root rather than
  the current working directory, so they fire correctly regardless of where the
  agent is invoked from. Because skill/hook scaffolding is version-gated on
  `.klaussy-version`, existing installs only pick this up on a re-run after the
  version bump (or with `--force`).

### Changed

- **`humanize` cuts over-explanation, not just surface AI tells** — the humanize
  skill now also trims redundant scaffolding and over-explanation rather than
  only stripping em-dashes and filler openers, producing tighter prose. The
  deterministic scrubber backstop is unchanged.

## [0.11.0] - 2026-06-28

### Added

- **Faster review orchestration** — the `review` skill's Phase 3 validation now
  fans out: when sub-agents return more than 6 findings, it spawns parallel
  validation sub-agents (one per batch) instead of a single sequential pass,
  cutting the slowest serial stretch of a large review. Also added optional
  model-tiering guidance — run the mechanical Scope & Conventions lens on a fast
  model, keep the reasoning-heavy lenses and validators on the default model
  (saves cost; latency comes from the parallel validation). Cross-sub-agent
  prompt caching is intentionally *not* attempted: Claude Code gives each named
  sub-agent a separate cache, so it isn't controllable from a skill — and
  review-prep already shrank the per-sub-agent diff prefill.
- **`klaussy review-prep` + faster review skill** — a deterministic diff
  pre-processor that trims a branch diff to the reviewable files (dropping
  lockfiles, generated/vendored trees, minified/binary blobs, and pure renames)
  and emits an explicit manifest of what it excluded. The `review` skill's
  Phase 1 now sources its diff from `review-prep` (falling back to `git diff`
  when the CLI isn't on PATH) and triages on the trimmed line count, so the
  model reads far fewer tokens on noisy PRs. On a representative diff this cut
  the input from 631 to 11 lines (~98%).
- **`slop-coded` skill** — the joke inverse of `humanize`. Takes clean human
  prose and inflates it into maximal AI slop (em-dashes, filler openers, the
  "it's not X — it's Y" reframe, "and that's the whole point", emoji bullets,
  the *delve/tapestry/testament* lexicon). For demos and stress-testing the
  humanizer, not real deliverables. Preserves facts and never touches code.

## [0.10.0]

### Added

- **Dependency gate hook** — a new cross-agent guard that blocks package-manager
  commands adding a *new named* dependency (`pip install requests`, `npm install
  lodash`, `poetry add`, `cargo add`, `go get`, …) so the agent confirms it's
  actually needed before bloating the manifest. Bare manifest syncs (`npm
  install`, `pip install -r requirements.txt`, `uv sync`) pass through untouched;
  prefix a confirmed install with `KLAUSSY_DEPS_OK=1` to proceed. Wired into all
  seven agents with a pre-shell hook (Claude, Gemini, Cursor, Codex, Copilot,
  Antigravity, Cline).
- **`adr-generator` skill** — drafts Architecture Decision Records, matching the
  repo's existing ADR location and template (MADR/Nygard) or establishing one.
- **`security-audit` skill** — a focused, diff-scoped security pass (secrets,
  injection, SSRF, access control, unsafe deserialization, new/vulnerable
  dependencies); narrower and deeper than the general `review` skill.
- **Shared session state** — `klaussy init` scaffolds `.agents/session.json`, a
  tool-neutral handoff note (branch, task, plan, known failures) any agent can
  read at session start and update as work progresses, so switching between tools
  doesn't mean re-discovering the active task. Live state is gitignored; the
  committed `.agents/SESSION.md` documents the contract.

### Fixed

- Capability banners are now detected against the *adapted* skill body, so a
  sub-agent / plan-mode mention inside a stripped dynamic-shell block no longer
  triggers a spurious banner.

## [0.9.0]

### Added

- **Aider (Ollama) backend** — model-agnostic, commonly run on a local Ollama
  model. Emits a flat `CONVENTIONS.md` (project-wide conventions + inlined
  path-scoped rules) wired into `.aider.conf.yml`'s `read:` key,
  `auto-lint`/`lint-cmd` + `test-cmd` gating, and `.aiderignore` read blocks.
  Aider has no skills/hooks mechanism, so those steps are skipped with an honest
  note.

## [0.8.0]

### Changed

- Commit guard is now scoped to the diff, and a verbose-comment check was added.

## [0.7.1]

### Changed

- `plan` skill: refreshed the Phase 5 approval template.

## [0.7.0]

### Added

- Full **Cline** backend support.

## [0.6.0]

### Added

- **Comment guard** — a new hook, wired into every agent, that humanizes the
  agent's outgoing `gh` comment (`gh pr comment` / `issue comment` / `pr
  review`) before it posts. On Claude it rewrites the command in place via the
  `PreToolUse` `updatedInput` field; on the other agents (which can't rewrite
  tool input) it blocks the post and returns the humanized command to re-issue.
- `klaussy.toolkit` — a public Python library surface for every scaffolding
  operation (`init`, `skills`, `settings`, `hooks`, `github`, `checklist`,
  `humanize`, `humanize_files`, `status`), plus the `ScaffoldResult` type. No
  subprocess and no interactive prompts: the base branch is auto-detected and
  `agents` accepts a list, a single key, or `"all"`.
- MCP tools `klaussy_hooks`, `klaussy_github`, and `klaussy_humanize`, giving the
  server one tool per CLI command (alongside `klaussy_status`).

### Changed

- The `fix` and `test` skills now scope to `BASE_BRANCH...HEAD` plus the working
  tree instead of running tools over the whole repo (or, for `test`, a bare
  `git diff` that missed committed branch work).

### Fixed

- The git-commit guard now runs format/lint **scoped to the files being
  committed** instead of the entire repository, so pre-existing issues in
  untouched files no longer block an unrelated commit. The Claude guard also
  allows the commit when a checker binary is missing, matching the cross-agent
  guard.
- The MCP server's `klaussy_status` reported skills from a stale `SKILL_NAMES`
  copy that omitted `precommit` and `humanize`; it now uses the canonical list
  via `klaussy.toolkit.status`.

### Documentation

- README: added the `precommit` skill, badges, a table of contents, a
  generated-skill example, and an "As a Python library" section; condensed the
  per-piece descriptions and led with pre-commit and humanize.
