"""Explicit, additive examples for Scholar's real local library.

Nothing is seeded on import or by a GET. The caller supplies an authorized
user library root and an existing host-authorized project's slug; this module
never resolves users, selects projects, opens a store or downloads papers.
"""

from ._catalog import mnist_reference_bibtex, mnist_references
from ._seed import seed_mnist_library

__all__ = ["mnist_references", "mnist_reference_bibtex", "seed_mnist_library"]
