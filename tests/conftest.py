"""Test-suite setup.

Several suites import the guard templates directly to exercise them. Python
would drop a `__pycache__` next to each one, under `src/klaussy/templates/` —
which `package-data`'s `templates/**/*` glob then sweeps into the wheel, and
which dirties the tree on every run. Ask for no bytecode instead; `.pyc` files
were tracked and shipped for real before this.
"""

import sys

sys.dont_write_bytecode = True
