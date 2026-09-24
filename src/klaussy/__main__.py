"""Entry point for `python -m klaussy`.

The `klaussy` console script is the normal way in. This exists for the case the
skills fall back to: the package importable in the active environment while its
script directory is off PATH, which `pip install --user` produces routinely.
Without it the fallback raises "No module named klaussy.__main__".
"""

from __future__ import annotations

from klaussy.cli import main

if __name__ == "__main__":
    main()
