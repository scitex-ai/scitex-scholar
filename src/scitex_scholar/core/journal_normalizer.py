#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Journal Name Normalizer (compatibility shim).

The implementation lives in :mod:`scitex_scholar.core._journal_normalizer`;
this module re-exports its public surface so existing imports keep working.

Handles journal name variations, abbreviations, and historical names
using ISSN-L as the unique identifier (single source of truth).

Data sources:
- OpenAlex API (display_name, alternate_titles, abbreviated_title, issn_l)
- Local cache

Usage:
    from scitex_scholar.core import JournalNormalizer

    normalizer = JournalNormalizer.get_instance()

    # Normalize any journal name variant
    canonical = normalizer.normalize("J. Neurosci.")  # -> "Journal of Neuroscience"

    # Get ISSN-L for a journal
    issn_l = normalizer.get_issn_l("PLOS ONE")  # -> "1932-6203"

    # Check if two names refer to same journal
    normalizer.is_same_journal("J Neurosci", "Journal of Neuroscience")  # -> True

Lookups read the local cache only. Refreshing it from OpenAlex crawls the
whole journal corpus and takes minutes, so it is an explicit, out-of-band
call (``refresh_journal_cache()``) and never a side effect of a lookup --
see the package README for the defect that rule exists to prevent.
"""

from __future__ import annotations

from ._journal_normalizer import (
    CACHE_TTL_SECONDS,
    OPENALEX_POLITE_EMAIL,
    OPENALEX_SOURCES_URL,
    JournalNormalizer,
    get_journal_issn_l,
    get_journal_normalizer,
    is_same_journal,
    normalize_journal_name,
    refresh_journal_cache,
)
from ._journal_normalizer._cache import default_cache_dir as _get_default_cache_dir
from ._journal_normalizer._names import normalize_issn as _normalize_issn
from ._journal_normalizer._names import normalize_name as _normalize_name

__all__ = [
    "CACHE_TTL_SECONDS",
    "OPENALEX_POLITE_EMAIL",
    "OPENALEX_SOURCES_URL",
    "JournalNormalizer",
    "get_journal_issn_l",
    "get_journal_normalizer",
    "is_same_journal",
    "normalize_journal_name",
    "refresh_journal_cache",
]

# EOF
