# new-worktree

Pins the branch naming rules and the slash-free directory name.

## case: flattens-slash-in-directory

The branch keeps its `fix/` prefix, the directory doesn't nest under it.

### instruction
Output only the `git worktree add` command you would run.

### context
Repository folder: shop. Base branch: main.
Task: the login page redirects to /home instead of the page the user came from.

### expect
- matches: git worktree add \.\./shop-fix-[a-z0-9-]+ -b fix/[a-z0-9-]+ main
- not contains: ../shop-fix/

## case: feature-prefix-and-kebab-case

A new capability gets `feat/` and a lowercase kebab-case name.

### instruction
Output only the `git worktree add` command you would run.

### context
Repository folder: Billing_API. Base branch: develop.
Task: Add CSV Export For Invoices

### expect
- matches: -b feat/[a-z0-9]+(-[a-z0-9]+)+ develop
