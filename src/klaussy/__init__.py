"""klaussy — multi-agent repo boilerplate generator.

Beyond the CLI, klaussy is usable as a library. The public surface lives in
`klaussy.toolkit` (function names there deliberately match the internal submodules,
so they're namespaced under `toolkit` rather than dumped onto the package root):

    from klaussy import toolkit
    toolkit.init(repo=".", agents=["claude", "gemini"])
    toolkit.humanize("A great solution — it works.")
"""

__version__ = "0.17.1"

# Bind the library submodule so `import klaussy; klaussy.toolkit.…` works without a
# separate `import klaussy.toolkit`. Done after __version__ so the modules that read
# it during import find it defined.
from klaussy import toolkit  # noqa: E402, F401

__all__ = ["__version__", "toolkit"]
