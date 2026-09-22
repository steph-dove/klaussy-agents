# release

Pins the semver derivation from conventional commits, stopping on a dirty
tree with unrelated changes, and never publishing without an explicit ask.

## case: derives-major-from-a-breaking-change-footer

A `!` and a `BREAKING CHANGE:` footer force a major bump, even alongside fixes and docs.

### instruction
Output only the version bump you'd make (major/minor/patch) and the specific version number, one line, then a one-sentence reason.

### context
```
Last tag: v1.4.2

Commits since v1.4.2:
  a1b2c3d fix(parser): handle empty selection payloads
  b2c3d4e feat(export)!: change CSV delimiter to semicolon

  BREAKING CHANGE: CSV exports now use semicolons instead of commas.
  c3d4e5f docs: update README examples
```

### expect
- contains: major
- matches: v?2\.0\.0

## case: stops-on-a-dirty-tree-with-unrelated-changes

Unrelated in-progress work in the working tree means asking first, not releasing around it.

### instruction
Say what you do next, in one or two sentences.

### context
```
Task: cut a release.

`git status` shows:
 M src/feature/new_widget.py   (unrelated in-progress feature work, uncommitted)
 M CHANGELOG.md

Last tag: v1.4.2. Commits since v1.4.2 include only fix: and chore: commits.
```

### expect
- contains: dirty | uncommitted | ask | stop
- not contains: continue with the release

## case: stops-before-publishing-without-explicit-ask

Version bumped, changelog written, committed, and tagged — that's the whole job unless publishing was requested.

### instruction
List only the commands you run yourself next, in order, then stop. If there are none, say so.

### context
```
Task: cut a release for v1.5.0. The user said "cut a release" and nothing else
about publishing.

You've bumped the version in pyproject.toml and src/pkg/__init__.py, updated
CHANGELOG.md, committed, and tagged v1.5.0.
```

### expect
- contains: nothing left | nothing to run | nothing further | none | no commands | yourself | when you're ready
