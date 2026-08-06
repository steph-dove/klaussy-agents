"""Deprecated alias for `klaussy.pr_template`.

The template isn't GitHub-only any more, so the module moved. This shim keeps
`from klaussy.github import scaffold_github` working for anything pinned to the
old name; remove it in the next major version.
"""

from klaussy.pr_template import scaffold_pr_template

__all__ = ["scaffold_github", "scaffold_pr_template"]

scaffold_github = scaffold_pr_template
