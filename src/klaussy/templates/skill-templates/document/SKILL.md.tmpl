---
name: {{REPO}}-document
description: Use when the user wants documentation written or updated — docstrings, API docs, a README section, or a doc comment on a tricky piece of code. Documents selectively: what a reader genuinely can't infer from the code, and nothing they can. Writes prose, not code changes.
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Edit Write
---

Add documentation where it earns its place, and only there. The hard part of this skill is restraint: most code does not need a comment, and a docstring that restates the signature is worse than none — it rots, and it trains readers to skip comments. Document the *why* and the non-obvious; never the *what* the code already shows.

## Phase 1: Decide what actually needs documenting

1. **Read the target** — the file, module, or diff the user named (default to the current change if they named nothing). Read enough of the surrounding code to know what a reader could already infer.
2. **Match the repo's existing doc style.** Read a few already-documented files: docstring convention (Google / NumPy / reST / JSDoc / TSDoc), whether public APIs carry docstrings, how module headers look. Match it exactly — don't introduce a new style.
3. **Select ruthlessly.** Document something only if it clears this bar:
   - **Public API surface** — an exported function/class/module whose contract (params, return, raises, side effects) a caller needs and can't see from the body.
   - **Non-obvious *why*** — a workaround, an invariant, a performance trade-off, an ordering dependency, a link to an issue/spec that explains a surprising choice.
   - **A gotcha** — behavior that would surprise a competent reader (a subtle edge case, a footgun, a "must call X before Y").

   If a candidate doesn't clear the bar, **leave it undocumented** — that is the correct outcome, not a gap. Say plainly which things you deliberately left alone and why.

## Phase 2: Write it

1. **Comments/docstrings: explain intent, not mechanics.** A single line is usually enough. Never narrate steps ("loop over the items"), restate the signature, or echo a name. If the clearest fix is a better name instead of a comment, suggest that.
2. **Docstrings: state the contract concisely** — what it does, its params/return, and what it raises or mutates — in the repo's format. Skip the obvious; a one-line summary is fine when that's all the contract is.
3. **README / guide prose:** lead with what the reader needs to do or know; keep examples runnable and current; don't duplicate what's already documented elsewhere — link instead.
4. **Don't change code behavior.** This skill writes documentation. If documenting reveals a bug or a confusing API, report it (for the debug or refactor skill) rather than fixing it here.

## Phase 3: Verify

- **Re-read each doc against the code it describes** — an inaccurate comment is worse than none. Confirm params, return types, and described behavior actually match.
- If the repo builds docs (e.g. Sphinx, TypeDoc, mkdocs — check CLAUDE.md), build them to confirm nothing is malformed.

{{HUMANIZE}}

## Rules

- **Bias toward less.** When unsure whether something needs a comment, it doesn't. Under-documenting is a smaller sin than comment noise.
- One-line comments by default; reserve multi-line docstrings for genuine public-API contracts.
- Never add changelog/narration comments ("Added to fix…", "Now we handle…") or comments that restate the code.
- Don't document code you didn't read fully — a plausible-but-wrong doc is a trap for the next reader.
- Keep docs next to the code they describe; don't spawn a separate doc file when a docstring would do.

## When NOT to use

- The user wants code written or changed — that's implement/refactor; this skill only writes docs.
- The user wants a PR description or release notes — use the pr or release skill.
- The code is self-explanatory and the user just feels it "should have comments" — say so; adding noise to clear code makes it harder to read, not easier.
