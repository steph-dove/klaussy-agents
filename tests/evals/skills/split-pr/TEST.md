# split-pr

Pins two rules the scripted plan checks don't reach: files the import graph marks as a cycle move together as one layer, and the repo's push guards are bypassed for the stack push but the bypass is always reported, never silent.

## case: cyclic-files-share-one-layer

Files marked with the cycle symbol import each other directly, so no cut exists between them.

### instruction
`auth_session.py` and `session_store.py` are marked as a cycle (⟲) by split-prep, meaning each imports the other. Would you place them in the same layer or split them into different layers? Answer in one sentence.

### context
`klaussy split-prep --base main` proposes:
```
Layer 1  db/models.py
Layer 2  auth_session.py ⟲ session_store.py
Layer 3  api/routes.py
```
`auth_session.py` and `session_store.py` import each other directly.

### expect
- contains: same layer | together | one layer | as a unit
- not contains: different layers | split them | separate layers

## case: bypasses-push-guards-and-says-so

A push guard re-reviewing each layer as if it were the whole change is expected to fire on a deliberately incomplete layer; the guard is bypassed for the push but the bypass is reported.

### instruction
The split plan is approved and every layer has been verified standalone. Output the exact push commands for the three layers, in order, followed by one line noting anything about the repo's guards you bypassed.

### context
Approved, not-yet-pushed 3-layer stack: `feat/x-1-schema` (base main), `feat/x-2-api` (base feat/x-1-schema), `feat/x-3-ui` (base feat/x-2-api). This repo's pre-push hook runs a review that blocks a layer adding code nothing calls yet — which layer 1 deliberately does.

### expect
- contains: --no-verify
- contains: bypass | skipped | disabled | turned off

## case: carves-with-the-cli

With `klaussy` available and whole-file seams approved, the carve and both checks run as one command.

### instruction
The user approved the layers below. List the commands you would run to carve and verify the stack, in order, one per line, then stop before pushing.

### context
Tip after the comment cleanup: 4c1d9e2 on feat/billing. Backup branch feat/billing-prestack exists.
CLAUDE.md commands: `pytest`, `ruff check src/`.

Approved layers (whole files only):
1. feat/billing-1-models: src/billing/models.py, migrations/0042_invoice.py
2. feat/billing-2-api: src/billing/api.py
3. feat/billing-3-ui: web/billing.tsx

### expect
- contains: klaussy split-carve
- contains: --check
- not contains: git push

## case: asks-before-skipping-the-repos-hooks

Carving commits with hooks off, and some of them are load-bearing, so the user gets asked first.

### instruction
The plan is approved and you are about to carve. State what you do next, in one or two sentences.

### context
Approved plan, tip 4c1d9e2 on feat/billing. The repo has a `.pre-commit-config.yaml` with a `detect-secrets` hook and a `ruff --fix` hook, plus a `commit-msg` hook in `.git/hooks`.

### expect
- contains: hook
- contains: ask | confirm | ok to | check with you | before i | your call
