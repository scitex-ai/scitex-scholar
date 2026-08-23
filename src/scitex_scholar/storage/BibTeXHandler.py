#!/usr/bin/env python3
# File: src/scitex_scholar/storage/BibTeXHandler.py
"""
Handles BibTeX parsing, rendering, merging and project bibliographies.

The class inherits from mixins in ``._bibtex``, each owning one stage:
- BibTeXParsingMixin: BibTeX file/text -> Paper objects
- BibTeXWritingMixin: Paper objects -> BibTeX entries and files
- BibTeXMergingMixin: merge several .bib files, dedupe and reconcile papers
- BibTeXProjectsMixin: a project's info/bibliography/ tree and exports
"""

from __future__ import annotations

import scitex_logging as logging

from ._bibtex import (
    BibTeXMergingMixin,
    BibTeXParsingMixin,
    BibTeXProjectsMixin,
    BibTeXWritingMixin,
)

logger = logging.getLogger(__name__)

__all__ = ["BibTeXHandler"]


class BibTeXHandler(
    BibTeXParsingMixin,
    BibTeXWritingMixin,
    BibTeXMergingMixin,
    BibTeXProjectsMixin,
):
    """Handles BibTeX parsing and conversion to Paper objects."""

    def __init__(self, project: str = None, config=None):
        self.name = self.__class__.__name__
        self.project = project
        self.config = config


# EOF
