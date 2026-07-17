#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Journal name normalization, keyed by ISSN-L.

Public surface is re-exported here; `core/journal_normalizer.py` remains a
shim over this package so existing imports keep working.
"""

from ._cache import CACHE_TTL_SECONDS
from ._fetch import OPENALEX_POLITE_EMAIL, OPENALEX_SOURCES_URL
from ._names import normalize_issn, normalize_name
from ._normalizer import (
    JournalNormalizer,
    get_journal_issn_l,
    get_journal_normalizer,
    is_same_journal,
    normalize_journal_name,
    refresh_journal_cache,
)

__all__ = [
    "CACHE_TTL_SECONDS",
    "OPENALEX_POLITE_EMAIL",
    "OPENALEX_SOURCES_URL",
    "JournalNormalizer",
    "get_journal_issn_l",
    "get_journal_normalizer",
    "is_same_journal",
    "normalize_issn",
    "normalize_journal_name",
    "refresh_journal_cache",
]

# EOF
