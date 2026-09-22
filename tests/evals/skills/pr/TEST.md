# pr

Pins the end-state-not-changelog rule, dropping filler when there's nothing to
flag, and calling out database changes. The sections/tells/summary checks
already live in `test_pr_eval.py`.

## case: describes-end-state-not-the-detour

Abandoned approaches on the way to the fix don't belong in the summary.

### instruction
Output only the Summary section (`## Summary` and its text). Describe the current end state, not a changelog of how you got there.

### context
```
Branch: fix/cache-invalidation

Commit history vs base:
  a1b2c3d wip: try invalidating cache on read
  b2c3d4e revert previous approach
  c3d4e5f fix(cache): invalidate on write instead of read

Files changed:
  src/cache/store.py | 8 +++---
```

### expect
- contains: write
- not contains: first tried | initially | reverted | wip

## case: drops-filler-for-a-trivial-change

A one-line fix gets a short description, no invented "Notes".

### instruction
Output the full PR description for this branch.

### context
```
Branch: fix/typo-readme

Commit history vs base:
  a1b2c3d docs: fix typo in README

Files changed:
  README.md | 2 +-
```

### expect
- contains: typo | readme
- not contains: n/a | not applicable | nothing to add

## case: calls-out-database-changes

A migration file in the diff must be called out explicitly, not folded into a generic bullet.

### instruction
Output the full PR description for this branch.

### context
```
Branch: feat/add-user-role

Commit history vs base:
  a1b2c3d feat(db): add role column to users table
  b2c3d4e feat(api): expose role in user serializer

Files changed:
  migrations/0012_add_role.py | 15 +++++++++
  src/api/serializers.py | 6 +++--
```

### expect
- contains: migration | database | db
- contains: role
