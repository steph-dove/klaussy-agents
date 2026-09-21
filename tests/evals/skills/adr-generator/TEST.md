# adr-generator

Pins that an existing ADR convention is matched rather than replaced with a competing format, and that a new record defaults to `proposed` status unless the user says the decision is already final.

## case: matches-existing-nygard-style

A repo that already has ADRs gets a new one in the same template and the next sequence number, not a second competing format.

### instruction
Given the decision below, output only the new file's path and its section headings (not the prose).

### context
`docs/adr/` contains:
```
0005-use-kafka-for-events.md
0006-drop-graphql-gateway.md
```
`0006-drop-graphql-gateway.md`'s headings are: Status, Context, Decision, Consequences.

New decision to record: switch the cache layer from Memcached to Redis.

### expect
- contains: 0007
- contains all: Context | Decision | Consequences
- not contains: Considered options

## case: status-defaults-to-proposed

Status is `proposed` unless the user explicitly says the decision is already accepted.

### instruction
Output only the Status and Date lines you would write for this new record.

### context
No `docs/adr/` directory exists yet. Decision to record: adopt trunk-based development. The user has not said whether this decision is already final.

### expect
- contains: proposed
- not contains: accepted
