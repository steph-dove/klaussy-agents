# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Releases
before 0.6.0 are recorded in the git tags (`v0.2.0`–`v0.5.1`).

## [0.29.0] - 2026-08-18

### Fixed

- **The comment guard now actually runs.** klaussy ships fixes by having the
  package upgraded, but the guard was delivered as a copy into each repo's
  `.claude/hooks/`, with the hook command pointing at that copy. An upgrade
  never rewrote those copies, and the launcher exits 0 in silence when one is
  missing — so the guard a repo ran was frozen at whatever version scaffolded
  it, and did nothing at all in repos klaussy had never been run in. Every
  humanize fix shipped to that guard had been landing in a package the hook
  wasn't executing. `klaussy-hook` gains a `--packaged` mode that resolves a
  guard out of the installed package, and the comment guard is wired to it: it
  names no repo path, so it runs in every repo at the installed version and an
  upgrade reaches all of them at once. Guards that bake in repo conventions —
  the commit guard's format and lint commands, the plan and self-review
  dialects — stay per-repo copies.
- **PR and issue bodies are humanized, not just literal comments.** The guard
  only parsed a body passed as a single literal token, on three subcommands, so
  `--body-file`/`-F` (the shape anything multi-line uses) and every
  `gh pr create` body went straight past it. Those are now scrubbed in place
  before `gh` reads them, and `pr create`, `pr edit`, `issue create` and
  `issue edit` are covered. A file git reports as tracked is never rewritten,
  and a file git can't answer for is left alone rather than assumed safe.
  Writes go through a temp file and a rename, so a failed write can't hand `gh`
  a truncated body. Parsing is scoped to the `gh` command and splits the line
  quote-aware, so a chained `git commit -F msg.txt` isn't read as the comment
  body — and a body holding a markdown table isn't split apart.
- **Every outcome is reported.** Returning quietly once the guard knows a body
  has tells was indistinguishable from the body being clean, which is the
  failure it exists to prevent. Where the cross-agent guard can't scrub a body,
  it blocks with the reason rather than allowing a post with a note that may
  surface nowhere.

### Changed

- **`.claude/hooks/comment_guard.py` is no longer scaffolded**, and a copy left
  behind by an earlier version is removed on the next run. The guard runs from
  the package now, so a repo copy would be an inert file that reads as the
  live one.

## [0.28.1] - 2026-08-17

### Fixed

- **Session notes now carry `type`, the one field the Open Knowledge Format
  actually requires.** The session-context skill described these as OKF notes
  while the frontmatter it told agents to write left `type` out, so every note
  produced from the template was non-conformant against the spec the skill
  cites. Extra keys are legal under OKF and a missing required key is not, so
  the rest of the schema was fine; the claim was the part that was wrong. The
  reading step now also covers `stale_after`, and tells agents that a note past
  its expiry is history rather than current state.

## [0.28.0] - 2026-08-13

### Added

- **`session-context` skill.** Scaffolds the protocol that lets agents working
  one session read and write a shared notes channel, so a port that moved or a
  decision one agent made stops being invisible to the others. Notes are
  Markdown with YAML frontmatter, kept outside the repository, and the skill
  covers both the read path (treat notes as claims to verify, not fact) and the
  write path (write when another agent would otherwise discover it the hard
  way, stay quiet about routine progress).

## [0.27.0] - 2026-08-11

### Changed

- **The humanize skill runs in four passes instead of one.** Cut (content only,
  keeping every retained sentence word for word), voice (register only, with the
  facts frozen), check (did the meaning survive), then the deterministic
  scrubber. One prompt carrying every rule reliably applies the safe mechanical
  ones and drops voice and length, which is why humanized prose stayed tidy and
  generated-sounding however the rules were tuned. Splitting the job is what
  fixed it: on a 330-word technical reply the four passes land at 120-167 words
  with fragments and a stance, where the single pass sat near 200 and mirrored
  the draft's paragraph count. Below roughly 40 words it does voice and scrub
  only and says so.
- **The check pass is the guard the register push needed.** Cutting and
  restyling in separate turns means neither is verifying the claims survived, so
  the third pass diffs the rewrite against the original for anything added
  (including agreement the author never gave), dropped (a load-bearing noun,
  number, identifier, or path), or reversed. Two measured failures motivated it:
  a rewrite that turned "we invalidated the cache on every write" into "we
  invalidated on every write", and one that inverted a concession.
- **The shared block traded eleven bullets for three sections.** The mechanical
  tells the scrubber deletes deterministically (filler openers, scaffolding,
  apologies, praise, *actually*, *in order to*, *utilize*) collapsed to a single
  line pointing at the scrubber, freeing attention for what a model has to
  judge: a **Voice** section aimed at "a competent engineer typing this once, in
  a hurry, who isn't going to read it back", and an **Answer what was asked,
  then stop** section covering the closing principle, the mechanism nobody
  asked for, and granting a point without inflating it. The block had measurably
  hit capacity, where each new rule degraded compliance with the existing ones.

### Added

- **`klaussy humanize --rules`** prints the prompt-side block so another tool can
  embed the current rules instead of maintaining a copy that drifts. Written for
  klaussy-desktop, which builds its own review prompt when a worktree has no
  scaffolded skill.
- Evals for two surfaces that had none: replies to PR review feedback
  (`test_address_review_eval.py`, covering a review bot, a hostile reviewer, a
  request worth declining, and a one-word fix) and long-form humanizing
  (`test_humanize_longform_eval.py`), which is where the failures actually live.
  Every previously checked-in humanize fixture was short, and short prose always
  passed.

### Fixed

- **The scrubber reaches a fixed point in one run.** Every rule matches at the
  start of a line, so removing one tell promoted the next into that position
  where nothing re-examined it: "It's worth noting that actually the loop leaks"
  needed a second run to lose "Actually". It now iterates until the text stops
  changing (7 of 8 sampled inputs needed that second pass).
- Chatbot sign-offs beyond the exact phrase `Happy to help` are stripped, so
  "Happy to dig into a hybrid if you see an angle I'm missing" no longer survives
  a review reply. Mid-sentence prose ("she was happy to see it land") is left
  alone.

## [0.26.0] - 2026-08-11

### Added

- **The split-pr skill builds an actual stack now, not three pull requests that
  happen to chain.** GitHub shipped native stacked pull requests, so where the
  host has one the skill registers it and the request pages carry a stack map,
  navigation between layers, and cascading rebase. The `{{FORGE}}` block for
  GitHub gained the `gh stack` commands and the two constraints that decide
  whether a stack is possible at all: every branch in one repo, and the
  `gh-stack` extension installed. Where the extension is missing the skill
  offers to install it, at the Phase 3 approval gate rather than mid-push, so
  the run interrupts once instead of twice. GitLab and Bitbucket say plainly
  that they have no native stack object, which turns "register a stack where the
  host has one" into a definite answer everywhere instead of a hunt for a
  feature that isn't there.
- **The stack records its own topology.** Each layer above the bottom gets
  `branch.<child>.klaussyParent` written to git config. The restack skill has
  always read exactly that key and until now nothing wrote it, so every stack
  split-pr built made restack re-derive the chain from commit ancestry.

### Changed

- **Phase 6 is a procedure rather than a sentence.** Push and open interleaved
  bottom-up, because a parent has to exist on the remote before a child can
  target it, and the base is passed explicitly on every request and then read
  back off it. That field silently defaults to the repo's default branch when
  omitted, which puts every layer on the base and makes each request show the
  sum of everything under it, the exact review problem the split existed to
  solve.
- **The repo's own guards come off during a carve.** A commit hook that formats,
  lints with a fix flag, or applies review suggestions treats each layer commit
  as fresh authorship and rewrites it, which is the one edit the carve phase
  forbids arriving from the direction nobody watches. A guard already running is
  never interrupted either: a formatter killed halfway leaves its edits staged
  for the next commit to swallow. At push time the same guards judge each layer
  as though it were the whole change, so they refuse over exactly the seams that
  were designed on purpose, and re-read the same lines once per layer. Both were
  found by running the skill end-to-end rather than by reading it.
- `kimi_hooks` no longer carries a comment restating its own docstring five
  lines below it.

## [0.25.0] - 2026-08-07

### Changed

- **The shared humanize block now covers voice and shape, not just tells.** It
  was a list of things not to write; stripping those leaves prose that still
  reads like a model wrote it, because the register never changed. Two sections
  were added. *Voice*: say it out loud, contractions, verbs instead of noun
  phrases ("this validates the token", not "performs validation of the token"),
  a named subject doing the work, one idea per sentence. *Shape*: explicit
  budgets, lead with the change rather than the discovery, three sentences to a
  paragraph, prose instead of headings and bold field labels. Overlapping rules
  were merged (praise, ranking, and thanking a bot were three rules for one
  habit), and the em-dash rule moved above everything else, since the restructure
  had buried the strongest tell twenty bullets deep.
- **Review findings are prose, not a form.** The per-finding template of four
  bold field labels is gone: one finding is a metadata line plus one to three
  sentences leading with the fix. "Preserve full detail" became "four things stay
  (severity, `file:line`, trigger, fix), everything else is cuttable", and the
  final summary lost its checkbox grid and its "Review method" footer. The same
  format applies in the sub-agent scaffold and the validation sub-agent, so
  nothing re-inflates on its way through synthesis. Unrelated problems get their
  own entries; a single finding whose fix touches three files stays one entry.
- The explain skill leads with a two or three sentence answer instead of filling
  a four-bullet outline, and `pr`, `commit`, `address-review`, and
  `adr-generator` grew caps against padding a short change into a long write-up.
- **The scrubber keeps numeric ranges tight.** `35–50 min` becomes `35-50 min`
  rather than `35 - 50 min`, which read as a subtraction. Deliberately diverges
  from klaussy-desktop's previous behavior; that copy has been updated to match.

### Added

- **Stiff phrasings with one unambiguous short equivalent are now scrubbed
  deterministically**: `prior to` → `before`, `due to the fact that` → `because`,
  `in the event that` → `if`, `is able to` → `can`, `subsequent to` → `after`,
  and a few more. Replacements preserve the first letter's case, which also fixes
  a standing bug where a sentence-initial `Utilize` became a lowercase `use`.
- Filler openers now match their uncontracted form, so "It is worth noting that"
  is stripped alongside "It's worth noting that".
- Evals for the two new axes: stiff input must come back in spoken register under
  a word budget, and an over-structured finding (heading, metadata block, bold
  field labels, bullets, sign-off) must flatten to prose.

### Fixed

- **klaussy-desktop's JS port is back in lockstep with `humanize.py`.** It had
  been missing the `actual`/`actually` rules and the editorializing openers
  (`Personally`, `Honestly`, `IMO`) entirely, on top of everything added here.
  Both implementations now produce identical output across a 66-case corpus.

## [0.24.0] - 2026-08-06

### Added

- **New `split-pr` skill: turn an oversized change into a stack of dependent
  PRs.** It works from committed history or an uncommitted tree, backs the
  original up to a `<branch>-prestack` branch before touching anything, carves
  layers bottom-up, and opens one request per layer targeting the layer below.
  Two invariants are non-negotiable: the top of the stack must reproduce the
  carve source exactly (`git diff` printing nothing), and every layer must build
  and pass on its own — a layer that can't stand up means the seam wasn't real,
  and the fix is to merge it into its neighbour rather than loosen a test.
  Explicit-only, like `restack`; it creates a stack, `restack` repairs one.
- **`klaussy split-prep` proposes the layers from the import graph** instead of
  guessing from paths. Python is parsed with `ast` and JS/TS through its
  import/require statements, edges are kept only where both ends are in the same
  change, and the layers come off a topological sort — so a file in layer 1
  provably imports nothing above it. Files that import each other are reported as
  one unsplittable group; languages it can't parse are listed as ungraphed rather
  than placed on a guess, since a wrong edge proposes an order that can't build.
  Static imports only: runtime wiring (DI containers, registries, routing tables,
  filename-ordered migrations) produces no edge, and the output says so.
- **The split decision is made on code lines, not raw diff lines.** Comment bloat
  is the most common reason a change looks like it needs splitting when it
  doesn't, so `split-pr` tightens the comments the change added — following the
  same `comment-cleanup.md` rules the precommit guard uses, committed on its own
  — and only then measures and decides. "1,240 lines, 830 after stripping 410
  lines of comment, one PR is fine" is a supported answer.

### Changed

- `comment_lint.comment_records()` is now a public function. The extractor
  dispatch was buried inside `analyze()`, so a caller wanting the comments rather
  than findings about them would have had to reimplement it; `split_prep` uses it
  to size a diff, which keeps one definition of what counts as a comment.
- Eval `run_skill()` takes a `timeout`. A long multi-phase spec asked to
  enumerate a command plan can outrun the 240s default, and that's a harness
  limit rather than a failing spec.

## [0.23.0] - 2026-08-05

### Changed

- **QA captures screen recordings, not just screenshots.** The `qa` skill
  treated a screenshot as the evidence for a UI change, but a still frame shows
  one moment of a flow rather than the flow working. Video is now the expected
  artifact wherever the change has an interaction or more than one step, with
  screenshots as the fallback. A new section ranks the capture options and takes
  the first one already available: the repo's own e2e tooling (Playwright's
  `video` config, Cypress, Puppeteer's `page.screencast`), then the agent
  surface's browser control, then the browser's or the OS's recorder, then
  `asciinema` for terminal sessions. Nothing gets installed just to record.
  Backend changes visible through a dashboard get recorded too, as do
  interactive CLI sessions. Artifacts land in the same
  `Downloads/<repo>-<branch>` folder as before, now with names that say what
  they show and a warning to move videos out of the test runner's output
  directory before the next run overwrites them.
- **`rest-of-the-owl` requires a recording where one is possible.** The run is
  unattended, so the recording is often the only chance a human gets to watch
  the change work before merging. The PR body now names each media file and what
  it shows, since no forge CLI uploads images or video and the user drags them
  in by hand, and the final report says which artifacts still need attaching.

Two new rules come with this: a recording is the evidence rather than a nice
extra, and don't record secrets — capture the app window instead of the whole
desktop, and check the file before pointing anyone at it. The `run` skill is
deliberately unchanged; it drives the app so the agent can observe, while `qa`
is what produces artifacts for someone else.

## [0.22.0] - 2026-08-05

### Added

- **Skills adapt to your hosting provider.** Skills that touch a ticket, a
  pull/merge request, or CI hardcoded `gh`, which quietly made them
  GitHub-only. The provider is now detected once from `origin` and one tailored
  command block is substituted into `restack`, `address-review`, and
  `rest-of-the-owl`, the same mechanism as the shared humanize block. A GitLab
  repo's skills ship `glab mr` commands and discussion semantics rather than
  `gh pr` and review threads. Detection matches the *host*, so a repo named
  `github-actions-demo` hosted elsewhere isn't misread, and enterprise hosts
  like `github.acme.com` are picked up. A provider klaussy can't identify gets
  a block that tells the agent to ask rather than invent an endpoint.
- **The host's CLI is allow-listed.** Generated permissions include `Bash(gh *)`
  or `Bash(glab *)` for the detected host, in both the Claude settings and the
  prefix-based agents, and `grant-permissions` learned to look the CLI up from
  `origin` — no marker file announces it the way `pyproject.toml` announces
  pytest. Bitbucket gets nothing: it's driven with `curl`, which reaches far
  past the forge, so that prompt is worth keeping.
- **`klaussy pr-template` writes the template where the host reads it.** Every
  init wrote `.github/PULL_REQUEST_TEMPLATE.md` regardless of provider, inert
  on two of three. GitLab now gets `.gitlab/merge_request_templates/`, and
  Bitbucket is skipped with a reason, since its default description is a repo
  setting rather than a tracked file. An undetected host keeps the GitHub
  layout and says so, with `--forge` to override.

### Changed

- **`klaussy github` is now `klaussy pr-template`** across the CLI, the MCP
  tool (`klaussy_pr_template`), and the toolkit (`toolkit.pr_template()`). The
  old names still work as deprecated aliases and will be removed in the next
  major version.

### Fixed

- The Bitbucket command block was a caveat rather than commands, because
  Atlassian's REST reference doesn't render for retrieval. Reading the
  published OpenAPI spec directly established that threads are real (a reply is
  a comment carrying `parent.id`), that resolution has its own endpoint, and
  that retargeting is documented — along with the constraint nobody mentions,
  that only open requests can be mutated.
- GitLab thread resolution is documented per-discussion *and* per-note; the
  block previously claimed the latter didn't exist. Boolean fields need `-F`,
  since `-f` sends the literal string.

### Added (opencode)

- A local **Ollama provider** in the generated `opencode.json`, so a scaffolded
  repo can point opencode at a model on the machine. Declaring it costs nothing
  when Ollama isn't installed.

### Internal

- Evals for the restack skill, run against a live model, pinning what decides
  whether history survives a restack: `--onto` off the parent's recorded old
  tip, bottom-up order, leased force-pushes, and never the base branch. The
  eval harness was substituting every token except `{{FORGE}}`, so it had been
  judging a spec no scaffolded repo is ever served.

### Documentation

- README: how to invoke the skills after `klaussy init` — the
  `/<your repo name>-<skill>` form, the naming rule for repo names with
  capitals or spaces, and which skills never auto-trigger.

## [0.21.0] - 2026-08-05

### Added

- **`<repo>-restack` skill** — rebases a stack of dependent branches after the
  base moved, the bottom branch landed, or a mid-stack branch was amended. The
  parent/child chain comes from git ancestry (`merge-base --is-ancestor`, with
  the nearest ancestor winning) rather than from PR metadata, so it works the
  same on GitHub, GitLab, Bitbucket, or no forge at all, and the confirmed
  mapping is stored as `branch.<child>.klaussyParent` so later runs don't
  re-derive it. Each branch is rebased `--onto` its new parent off the parent's
  recorded old tip, which is what keeps a child from replaying its parent's
  commits a second time, and the result is verified with `range-diff`. A parent
  that landed by squash or rebase merge is detected by comparing trees
  (`merge-tree --write-tree`), since those rewrite SHAs and slip past ancestry.
  Force-pushes are leased and bottom-up, never on the base branch. Retargeting
  the PR/MR base is the only forge-dependent step, runs last, and prints the
  remaining manual steps rather than failing when no CLI is available.

### Fixed

- Cap `mcp` below 2.0 so the test suite runs against the supported FastMCP API.

### Documentation

- README: `<repo>-restack` in the skills table; the downloads badge reports
  total installs rather than the last month.

## [0.20.0] - 2026-07-26

### Added

- **Kimi Code CLI (Moonshot) as a tenth backend** — `klaussy init --agents kimi`.
  Conventions go to `.kimi-code/AGENTS.md` rather than the root `AGENTS.md` the
  Codex/Antigravity/opencode backends own: Kimi discovers AGENTS.md at a fixed
  set of paths with no subdirectory scanning, so path-scoped rules are inlined
  under their globs instead of split into nested files it would never read. The
  pre-plan guardrails ride that same file, since Kimi's context-injection hook
  isn't available from the repo. Skills land in `.kimi-code/skills/` (Kimi also
  reads `.agents/skills/`, but Codex and Cline already write there).
- **Kimi hooks and permissions as paste-in snippets.** Kimi loads `[[hooks]]` and
  `[[permission.rules]]` only from the user-level `~/.kimi-code/config.toml` —
  its project-local `.kimi-code/local.toml` accepts a `[workspace]` table only,
  and an unknown key fails the whole config load. So the guards are committed to
  `.kimi-code/hooks/` and the wiring is written to `.kimi-code/klaussy-hooks.toml`
  and `.kimi-code/klaussy-permissions.toml` to paste once. Commit, comment-humanize and
  dependency guards match `^Bash$`, the read-injection guard matches `^Read$`
  (anchored, so it skips `ReadMediaFile`), and the self-review guard runs on
  `Stop` via a new `kimi` dialect that blocks with exit 2 + stderr. Web-fetch
  scanning is left out: Kimi's `PostToolUse` can't block.
- **`klaussy-hook --repo-relative <path>`** — the launcher resolves a guard
  against the enclosing git repo and fails open outside one. Kimi's hooks are
  global config, so the command can't hardcode a repo path, and its four-field
  hook schema has no per-OS override; doing the resolution in the launcher keeps
  one command string working in sh, cmd, and PowerShell alike. Kimi is ✅/✅ in
  the README cross-platform matrix.

### Documentation

- README: Kimi in the hero line, the supported-agents list and the cross-platform
  table, and the agent count moved from nine to ten. The Codex row is now labelled
  **Codex CLI (OpenAI)** — klaussy always supported OpenAI's agent but never said
  so — alongside a note that these targets are agent tools rather than model
  vendors, so GPT users reach klaussy through Codex, aider, or opencode.

## [0.19.3] - 2026-07-25

### Added

- **Three new rules in the shared humanize block**, so every prose-output skill
  picks them up. No `actual` or `actually`, and no swapping in
  `real`/`really`/`genuinely`/`truly` — all of them are empty emphasis, and "it
  actually works" is "it works". No invented consensus (`most people expect
  this`, `everyone does it this way`, `it's widely considered best practice`) —
  argue from the code, a repo convention, or a linkable source, or own the claim.
  And no `nobody asked for this` or its paraphrases, which read as a swipe at the
  author instead of an objection about the code.
- **The scrubber enforces the first rule deterministically.** `Actually` joins the
  filler-opener list, and new rules drop the adverb mid-sentence, at a sentence
  start, and trailing with its comma. The adjective goes only after a determiner
  that doesn't inflect, so "an actual bug" never becomes "an bug", and only when
  the next word can head a noun phrase, so "compare the actual to the expected"
  is left intact. `real` stays prompt-side entirely, since deleting it flips
  meaning ("real user data, not fixtures").
- **`slop-coded` gained the matching tells** (empty emphasis, invented consensus)
  so the evil twin still produces what humanize strips.

### Changed

- The `review` and `slop-coded` skill templates drop their own uses of the words
  the new rules ban.

**Note:** `examples/fastapi` and `examples/httpx` still carry the 0.19.2 skill
output and will be regenerated in a later release.

## [0.19.2] - 2026-07-17

### Fixed

- **The commit guard now runs when a commit stages its own files.** An agent that
  writes `git add -A && git commit` fires the pre-commit gate before the `add`
  half runs, so the index is still empty when the guard asks git what's staged.
  Every path-scoped check — comment-lint, secret-scan, format, lint — resolved to
  zero files and was silently skipped, and the commit went through unjudged. The
  guard now detects a `git add` earlier on the same command line and folds the
  working tree into the paths it checks, the same way it already handles
  `git commit -a`. Fixed in both guard templates.
- **`comment-lint` findings stay on one line.** Each finding was printed through
  rich's console, which wrapped it to a second line at the terminal width. The
  comment-lint, import-lint, and secret-scan output now prints with soft-wrap off.

### Changed

- **Requires `klaussy-repo-conventions >= 1.6.0`**, which broadens language
  coverage in the discover step. Same CLI and `CLAUDE.md` output, so nothing else
  changed.

## [0.19.1] - 2026-07-16

### Fixed

- **`grant-permissions` no longer hands every agent Claude's tool names.** Step 4
  listed `Read`/`Edit`/`Write`/`Grep`/`Glob` flat, as if universal. They're Claude
  Code's vocabulary: Gemini gates `read_file`/`write_file`/`replace`, and opencode
  has no per-tool names at all — its `permission.read` / `permission.bash` maps
  cover this instead, so `Write` grants nothing there. The per-agent note already
  said to translate the rule syntax; it now says it for the tool names too.
- **Stop shipping compiled bytecode.** Nine `.pyc` files under
  `templates/**/__pycache__/` were tracked in git, so every release built them
  into the wheel — `package-data`'s `templates/**/*` glob sweeps them up, and
  `.gitignore` doesn't apply to files already tracked. Untracked, and the test
  suite now sets `sys.dont_write_bytecode` so importing a guard template stops
  leaving them behind.

### Internal

- The guard templates are now checked whole-file against klaussy's own comment
  and import gates. A scaffolded repo receives each template entire, so every
  line lands in that first commit's diff — while in this repo the same gate is
  diff-scoped and hides anything nobody has touched since. That gap shipped a
  blocking template in 0.18.1 and again in 0.19.0, both caught only by
  regenerating examples.

## [0.19.0] - 2026-07-16

### Added

- **`grant-permissions` grants the file tools, not just the commands.** The
  allow-list covered the stack's commands but left `Write` out, so the agent
  still stopped to ask before creating a file, and the builtins listed `rg`,
  `find` and `sort` but not `grep`. It now matches the Read/Edit/Write/Glob/Grep
  baseline `klaussy settings` has always written, and adds `Bash(grep *)`,
  `Bash(diff *)` and the everyday moves `cp`/`mv`/`touch`. Not `rm` — deleting is
  the one routine command worth a prompt. The safe-boundary section now also
  states that bare file tools allow any path the denies don't cover, not only
  paths inside the repo.

### Fixed

- **A commit-guard check that can't run no longer blocks the commit.** The guard
  treated any non-zero exit as findings, so a `klaussy` older than the guard
  exited 2 on an unknown subcommand ("No such command 'import-lint'") and every
  commit blocked on a usage error the message never explained — hit for real
  where a repo was scaffolded from a venv install while PATH resolved an older
  pipx one. Exit 2 means the tool couldn't judge the diff; 1 means it judged and
  found problems. ruff, eslint and Typer/Click all draw that line, so the guard
  now does too, matching the fail-open it already applied to a tool that isn't
  installed at all. It says so rather than skipping quietly: a silent skip is
  indistinguishable from a clean pass, and that's the wrong thing to imply about
  a secret scan that never ran.

## [0.18.1] - 2026-07-16

### Fixed

- **The self-review guard template no longer trips klaussy's own comment gate.**
  Its header comment ran to three sentences, over the two-sentence cap shipped in
  0.17.0. It stayed invisible because the gate scopes to changed lines and nobody
  had touched those two — it only surfaced when the whole file landed as new
  (regenerating `examples/`), which is what any repo scaffolding this guard for
  the first time sees.

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
