# fix

Pins the boundary between a style/type fix and a real bug, the scope-to-changed-files
rule, and the format-then-lint-then-type-check order.

## case: stops-on-real-bug-instead-of-papering-over-it

A type error that reveals a missing argument is a bug, not a type-fix — no cast, no `Any`, no `# type: ignore`.

### instruction
Decide whether to fix this or stop and report it as a bug. Output your decision in one or two sentences. Do not edit the file.

### context
```
File src/orders.py:
    def charge(amount, currency):
        return gateway.charge(amount)

mypy reports:
    src/orders.py:2: error: Missing positional argument "currency" in call to "charge" of "Gateway"  [call-arg]
```

### expect
- contains: bug | stop
- not contains: type: ignore | cast(

## case: ignores-violations-outside-the-changed-files

A pre-existing lint violation in a file this branch didn't touch stays alone.

### instruction
List exactly which findings you will fix, one per line, and nothing else.

### context
```
Changed files this branch: src/api/client.py

`ruff check` reports:
    src/api/client.py:14:5  E501  line too long (92 > 88 characters)
    src/legacy/report.py:3:1  F401  `sys` imported but unused
```

### expect
- contains: client.py:14
- max lines: 1

## case: runs-format-then-lint-then-type-check

Format runs first, lint second, type-check last.

### instruction
List the commands you would run, in order, then stop.

### context
```
CLAUDE.md commands:
  Format: ruff format
  Lint: ruff check --fix
  Type-check: mypy

Changed files this branch: src/foo.py
```

### expect
- matches: (?is)ruff format.*ruff check.*mypy
