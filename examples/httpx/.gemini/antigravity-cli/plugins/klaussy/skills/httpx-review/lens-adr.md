# Lens: Architecture Decision & Design Doc

## Look for: the quality of the architecture decision / design doc itself

You are reviewing a design artifact, not just code. Apply this rubric (drawn from
the Nygard ADR format, MADR, Rust RFCs, and "Design Docs at Google"). For each gap,
quote the doc section (or note its absence) and explain what's missing and why it
matters.

### Decision quality
- **Problem/context is concrete** — the doc states the problem and forces at
  play, not a vague preamble. Flag a problem statement so generic it could precede
  any decision.
- **The decision is explicit** — there is an unambiguous "we will do X" outcome, not
  just discussion that trails off.
- **Alternatives considered, with reasons rejected** — at least one real alternative
  is evaluated and the rejection is justified. A decision with no alternatives is the
  "Sprint" anti-pattern; flag it (High — this is the single most common ADR defect).
- **Decision drivers / criteria** — the factors behind the choice are named, and when
  they conflict, prioritized.
- **Consequences are honest** — both positive AND negative consequences are stated.
  Only-upside docs are the "Fairy Tale" anti-pattern; flag missing trade-offs.
- **Reversibility** — is this a one-way or two-way door? High-cost-to-reverse
  decisions deserve more scrutiny and should say so.
- **Scope** — goals AND non-goals are stated. Unbounded scope is a smell.

### Lifecycle & consistency
- **Status** — a valid lifecycle value is present (proposed / accepted / deprecated /
  superseded). A doc with no status is incomplete.
- **Supersession** — if this decision replaces an earlier ADR, it links to it (and
  ideally the old one is marked superseded). Flag a decision that silently contradicts
  an existing ADR in the repo without superseding it.
- **Code-vs-decision consistency** — if the same PR also changes code, verify the code
  implements the decided design. Flag drift between "we will do X" and code
  that does Y. This is the highest-value check a PR-time review can make that a
  standalone doc review cannot.

### Cross-cutting
- Security, privacy, operational, and maintenance implications are considered
  (or explicitly out of scope). For decisions with backwards-incompatibility, the doc
  should call out the migration/compat impact.

### Anti-patterns to name explicitly
- **Sprint**: only one option; only short-term effects considered.
- **Fairy Tale**: shallow justification, pros only, no cons.
- **Ghost architecture**: code makes an architecturally significant choice that the doc
  doesn't record (or vice versa).
- **Rubber-stamp**: a "decision" written after the fact to legitimize code already
  merged, with no real evaluation.

Do not nitpick prose, grammar, or formatting — that is not your job. Focus on whether
the decision is sound, honestly argued, and matches the code.

## Additional rules

- Severity guide: missing alternatives or missing consequences = High (the doc can't
  be trusted as a decision record). Code-vs-decision drift = High or Blocker depending
  on blast radius. Missing status/supersession links = Medium. Scope/cross-cutting
  gaps = Medium/Low.
- If the doc is genuinely complete and well-argued, say so in one line and return no
  findings. A good ADR is common; don't manufacture problems.
