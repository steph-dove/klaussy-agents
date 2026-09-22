---
name: fastapi-adr-generator
description: Use when the user wants to record an architectural decision — drafting an Architecture Decision Record (ADR) or RFC, documenting a design choice and its trade-offs, or capturing why an approach was taken. Detects the repo's existing ADR location and template style (MADR or Nygard) and matches it; if none exists, sets one up. Writes the record; it does not change code. Also known as `klaussy-adr-generator`.
allowed-tools: Read Grep Glob Bash(git log *) Write
---

You are drafting an Architecture Decision Record. An ADR captures one decision: the context that forced it, the choice made, and the consequences accepted. Follow these phases.

---

## Phase 1: Find the existing convention

Before writing anything, learn how this repo already records decisions so the new one matches.

- Look for an ADR directory: `docs/adr/`, `docs/decisions/`, `docs/architecture/decisions/`, `adr/`, or `rfcs/`. Use Glob/Grep.
- If records exist, read the two most recent. Match their template (MADR vs Nygard), heading style, status vocabulary, and filename scheme (`NNNN-title.md` is the common one).
- Determine the next sequence number from the highest existing file.
- If no ADR directory exists, default to `docs/adr/` with the MADR template below and start at `0001`. Tell the user you're establishing the convention.

Do not invent a second competing format when one is already in use.

## Phase 2: Gather the decision

You need enough to write each section truthfully. If the user's request already supplies it, don't re-ask — proceed. Otherwise ask only for what's missing:

- **Title** — the decision in a short noun phrase ("Use Postgres for the event store").
- **Context** — the forces in play: the problem, constraints, and what made a decision necessary now.
- **Options considered** — the alternatives and why each was or wasn't chosen.
- **Decision** — the option taken.
- **Consequences** — what this makes easier, what it makes harder, and any follow-up work or risk accepted.

Ground the context in the codebase where you can: cite the modules, dependencies, or `git log` history that motivated the decision rather than writing in the abstract.

## Phase 3: Write the record

Use the repo's established template if you found one. Otherwise use this MADR-style skeleton:

```markdown
# NNNN. <title>

- Status: proposed
- Date: <YYYY-MM-DD>
- Deciders: <who>

## Context and problem statement

<the forces and the problem, in a few sentences>

## Considered options

- <option 1>
- <option 2>

## Decision outcome

Chosen: **<option>**, because <justification>.

### Consequences

- Good: <what improves>
- Bad: <what we accept or take on>

## More information

<links to related ADRs, issues, or discussion>
```

Keep each section to a few sentences. An ADR earns its keep by being read six months later, and a long one won't be. Context is the forces that made a decision necessary, not a history of the codebase; consequences are what changes for whoever touches this next, not an exhaustive risk register. If a section has nothing real in it, leave it out rather than padding it.

Set status to `proposed` unless the user says the decision is already accepted. Write the file to the directory and filename scheme from Phase 1. Report the path back to the user and offer to mark it `accepted` once they confirm.

**Humanize anything a human will read.** Before prose ships — a PR body, a review comment or reply, a commit message, a changelog entry, docs — run it through the `fastapi-humanize` skill and use what comes back. That skill holds the rules; don't keep a second copy of them here.

**The scrubber is not that pass.** `klaussy humanize` deletes a fixed list of mechanical tells (dashes, filler openers, a few hedges) and changes nothing else. It can't cut a paragraph that shouldn't exist, turn a noun phrase back into a verb, drop the closing principle, or make three sentences one, and that's most of what makes prose read as generated. Anything a human will read gets the `fastapi-humanize` skill: cut, voice, check, then scrub. Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't stand in for it.
