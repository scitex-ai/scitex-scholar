#!/usr/bin/env python3
"""
Scholar storage module - Library and paper storage management.

Public API (actively used):
- LibraryManager: Low-level library operations
- ScholarLibrary: High-level library operations
- BibTeXHandler: BibTeX import/export and bibliography management
- BibTeXValidator: BibTeX file validation for syntax and content integrity
- PaperIO: Individual paper I/O operations

Internal (not for external use):
- _LibraryCacheManager: Used by ScholarLibrary
- _DeduplicationManager: Used by LibraryManager
"""

from ._BibTeXValidator import (
    BibTeXValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    validate_bibtex_content,
    validate_bibtex_file,
)
from ._LibraryCacheManager import LibraryCacheManager
from ._LibraryManager import LibraryManager
from ._master_store import add_paper as master_add_paper
from ._master_store import get_paper_path as master_get_paper_path
from ._master_store import list_papers as master_list_papers
from ._master_store import paper_id_for as master_paper_id_for
from ._search_filename import normalize_search_filename
from .BibTeXHandler import BibTeXHandler
from .PaperIO import PaperIO
from .ScholarLibrary import ScholarLibrary

__all__ = [
    "LibraryManager",
    "ScholarLibrary",
    "master_add_paper",
    "master_get_paper_path",
    "master_list_papers",
    "master_paper_id_for",
    "BibTeXHandler",
    "BibTeXValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "validate_bibtex_file",
    "validate_bibtex_content",
    "PaperIO",
    "LibraryCacheManager",
    "normalize_search_filename",
]
