#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/__init__.py
"""
Mixin classes for BibTeXHandler.

Each mixin provides one stage of the BibTeX lifecycle; ``BibTeXHandler``
composes them into the single public class.
"""

from ._comments import BIBTEX_AT_REPLACEMENT, sanitize_bibtex_comments
from ._merging import BibTeXMergingMixin
from ._parsing import BibTeXParsingMixin
from ._projects import BibTeXProjectsMixin
from ._writing import BibTeXWritingMixin

__all__ = [
    "BibTeXParsingMixin",
    "BibTeXWritingMixin",
    "BibTeXMergingMixin",
    "BibTeXProjectsMixin",
    "sanitize_bibtex_comments",
    "BIBTEX_AT_REPLACEMENT",
]


# EOF
