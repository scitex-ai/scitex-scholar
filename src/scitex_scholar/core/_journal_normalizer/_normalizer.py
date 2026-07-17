#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The JournalNormalizer: ISSN-L keyed journal name lookups.

THE HOT-PATH RULE lives here. Lookups load whatever is cached on disk and
never crawl the corpus; only an explicit refresh goes to the network. See
this package's README.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import scitex_logging as logging

from . import _cache, _fetch
from ._names import normalize_issn, normalize_name

logger = logging.getLogger(__name__)


class JournalNormalizer:
    """
    Journal name normalizer using ISSN-L as unique identifier.

    Handles:
    - Full names <-> abbreviations
    - Name variants (spelling, punctuation, capitalization)
    - Historical/former names
    - Publisher variations

    Lookups are served from the local cache. Refreshing that cache from
    OpenAlex is an explicit, out-of-band operation (`refresh()`), never a
    side effect of a lookup.
    """

    _instance: Optional[JournalNormalizer] = None

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache_dir = cache_dir or _cache.default_cache_dir()
        self._cache_file = _cache.cache_file(self._cache_dir)

        # Core mappings (ISSN-L is the key)
        self._issn_l_data: Dict[str, Dict[str, Any]] = {}  # ISSN-L -> metadata

        # Lookup indexes (for fast search)
        self._name_to_issn_l: Dict[str, str] = {}  # normalized name -> ISSN-L
        self._issn_to_issn_l: Dict[str, str] = {}  # any ISSN -> ISSN-L
        self._abbrev_to_issn_l: Dict[str, str] = {}  # abbreviated name -> ISSN-L

        # Stats
        self._last_updated: float = 0
        self._loaded = False
        self._journal_count = 0
        self._cold_warning_emitted = False

    @classmethod
    def get_instance(cls, cache_dir: Optional[Path] = None) -> JournalNormalizer:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(cache_dir)
        return cls._instance

    # ==================== Loading ====================

    def _load_from_cache(self) -> bool:
        """Populate indexes from the cache file. True if data was loaded."""
        data = _cache.load_cache(self._cache_file)
        if data is None:
            return False

        self._issn_l_data = data.get("issn_l_data", {})
        self._name_to_issn_l = data.get("name_to_issn_l", {})
        self._issn_to_issn_l = data.get("issn_to_issn_l", {})
        self._abbrev_to_issn_l = data.get("abbrev_to_issn_l", {})
        self._last_updated = data.get("timestamp", 0)
        self._journal_count = len(self._issn_l_data)
        self._loaded = True

        logger.info(f"Loaded {self._journal_count} journals from normalizer cache")
        return True

    def _save_to_cache(self) -> None:
        """Persist current indexes to the cache file."""
        _cache.save_cache(
            self._cache_file,
            {
                "journal_count": len(self._issn_l_data),
                "issn_l_data": self._issn_l_data,
                "name_to_issn_l": self._name_to_issn_l,
                "issn_to_issn_l": self._issn_to_issn_l,
                "abbrev_to_issn_l": self._abbrev_to_issn_l,
            },
        )

    def _ensure_indexes(self) -> None:
        """Make cached data available to a lookup. NEVER touches the network.

        Every public lookup goes through here. A stale cache is used as-is:
        journal identity moves on the scale of years, so serving year-old
        data beats blocking a user's request on a corpus crawl.

        With no cache at all, lookups answer from empty indexes -- which for
        this class's contract means "not known" (`get_issn_l` -> None,
        `is_open_access` -> False, both already the documented answer for an
        unrecognised journal). That is reported once, loudly, with the
        command that fixes it -- it is not a silent fallback.
        """
        if self._loaded:
            return

        if self._load_from_cache():
            if not _cache.is_fresh(self._last_updated):
                logger.warning(
                    f"Journal cache is {self.cache_age_hours:.0f}h old and in use "
                    f"as-is. Refresh out of band with "
                    f"`python -c 'from scitex_scholar.core import refresh_journal_cache; "
                    f"refresh_journal_cache()'`."
                )
            return

        # No cache on disk. Answer "not known" rather than crawl the corpus
        # inside somebody's request.
        self._loaded = True
        self._journal_count = 0
        if not self._cold_warning_emitted:
            self._cold_warning_emitted = True
            logger.warning(
                f"No journal normalizer cache at {self._cache_file}: journal "
                f"normalization and OA detection are DEGRADED (every journal "
                f"reads as 'not known'). This does NOT auto-fetch, because the "
                f"corpus crawl takes minutes and must not run inside a request. "
                f"Populate it with `python -c 'from scitex_scholar.core import "
                f"refresh_journal_cache; refresh_journal_cache()'`."
            )

    def refresh(self, max_pages: int = 500) -> None:
        """Crawl OpenAlex and rebuild the cache. Takes MINUTES; blocks.

        This is the only path that hits the network. Call it from a CLI, a
        scheduled job, or a warm-up step -- never from inside a user request.
        """
        logger.info("Refreshing journal normalizer cache from OpenAlex...")
        self._issn_l_data = {}
        self._name_to_issn_l = {}
        self._issn_to_issn_l = {}
        self._abbrev_to_issn_l = {}

        _fetch.fetch_journals_sync(
            add_source=self._add_journal,
            checkpoint=self._save_to_cache,
            max_pages=max_pages,
        )

        self._journal_count = len(self._issn_l_data)
        self._last_updated = time.time()
        self._loaded = True

        if self._journal_count > 0:
            self._save_to_cache()
            logger.info(f"Fetched {self._journal_count} journals from OpenAlex")
        else:
            logger.warning("Journal refresh fetched nothing; cache left unchanged")

    def ensure_loaded(self, force_refresh: bool = False, max_pages: int = 500) -> None:
        """Ensure indexes are available.

        Args:
            force_refresh: Crawl OpenAlex and rebuild the cache (minutes).
            max_pages: Page cap for that crawl.

        Without `force_refresh` this only reads the local cache. It will not
        silently escalate to a network crawl -- that was the old behaviour and
        it blocked every first search of the day for minutes before failing.
        """
        if force_refresh:
            self.refresh(max_pages=max_pages)
            return
        self._ensure_indexes()

    def _add_journal(self, source_data: Dict[str, Any]) -> None:
        """
        Add a journal to the normalizer from OpenAlex source data.

        Args:
            source_data: OpenAlex source object with display_name, issn_l, etc.
        """
        issn_l = source_data.get("issn_l")
        if not issn_l:
            return

        issn_l = normalize_issn(issn_l)
        display_name = source_data.get("display_name", "")
        abbreviated_title = source_data.get("abbreviated_title", "")
        alternate_titles = source_data.get("alternate_titles", []) or []
        issns = source_data.get("issn", []) or []
        is_oa = source_data.get("is_oa", False)

        # Store full metadata
        self._issn_l_data[issn_l] = {
            "canonical_name": display_name,
            "abbreviated_title": abbreviated_title,
            "alternate_titles": alternate_titles,
            "issns": [normalize_issn(i) for i in issns if i],
            "is_oa": is_oa,
            "publisher": source_data.get("host_organization_name", ""),
        }

        # Build lookup indexes
        # 1. Canonical name
        if display_name:
            self._name_to_issn_l[normalize_name(display_name)] = issn_l

        # 2. Alternate titles (variants)
        for alt in alternate_titles:
            if alt:
                norm_alt = normalize_name(alt)
                if norm_alt and norm_alt not in self._name_to_issn_l:
                    self._name_to_issn_l[norm_alt] = issn_l

        # 3. Abbreviated title
        if abbreviated_title:
            norm_abbrev = normalize_name(abbreviated_title)
            self._abbrev_to_issn_l[norm_abbrev] = issn_l
            # Also add without periods (common variation)
            self._abbrev_to_issn_l[norm_abbrev.replace(".", "")] = issn_l

        # 4. All ISSNs -> ISSN-L
        for issn in issns:
            if issn:
                self._issn_to_issn_l[normalize_issn(issn)] = issn_l
        self._issn_to_issn_l[issn_l] = issn_l  # Self-reference

    # ==================== Public API ====================

    def get_issn_l(self, journal_name: str) -> Optional[str]:
        """
        Get ISSN-L for a journal name.

        Args:
            journal_name: Any journal name variant, abbreviation, or ISSN

        Returns
        -------
            ISSN-L if found, None otherwise
        """
        self._ensure_indexes()

        if not journal_name:
            return None

        # Check if it's an ISSN
        if re.match(r"^\d{4}-?\d{3}[\dXx]$", journal_name.replace(" ", "")):
            norm_issn = normalize_issn(journal_name)
            if norm_issn in self._issn_to_issn_l:
                return self._issn_to_issn_l[norm_issn]

        # Try normalized name lookup
        norm_name = normalize_name(journal_name)

        # Check full names
        if norm_name in self._name_to_issn_l:
            return self._name_to_issn_l[norm_name]

        # Check abbreviations
        if norm_name in self._abbrev_to_issn_l:
            return self._abbrev_to_issn_l[norm_name]

        return None

    def normalize(self, journal_name: str) -> Optional[str]:
        """
        Normalize journal name to canonical form.

        Args:
            journal_name: Any journal name variant

        Returns
        -------
            Canonical journal name, or original if not found
        """
        issn_l = self.get_issn_l(journal_name)
        if issn_l and issn_l in self._issn_l_data:
            return self._issn_l_data[issn_l].get("canonical_name", journal_name)
        return journal_name

    def get_abbreviation(self, journal_name: str) -> Optional[str]:
        """
        Get abbreviated title for a journal.

        Args:
            journal_name: Any journal name variant

        Returns
        -------
            Abbreviated title if available
        """
        issn_l = self.get_issn_l(journal_name)
        if issn_l and issn_l in self._issn_l_data:
            return self._issn_l_data[issn_l].get("abbreviated_title")
        return None

    def get_journal_info(self, journal_name: str) -> Optional[Dict[str, Any]]:
        """
        Get full journal metadata.

        Args:
            journal_name: Any journal name variant

        Returns
        -------
            Dict with canonical_name, abbreviated_title, alternate_titles,
            issns, is_oa, publisher
        """
        issn_l = self.get_issn_l(journal_name)
        if issn_l and issn_l in self._issn_l_data:
            return {"issn_l": issn_l, **self._issn_l_data[issn_l]}
        return None

    def is_same_journal(self, name1: str, name2: str) -> bool:
        """
        Check if two names refer to the same journal.

        Args:
            name1: First journal name
            name2: Second journal name

        Returns
        -------
            True if both names resolve to the same ISSN-L
        """
        issn_l_1 = self.get_issn_l(name1)
        issn_l_2 = self.get_issn_l(name2)

        if issn_l_1 and issn_l_2:
            return issn_l_1 == issn_l_2

        # Fallback: simple normalization comparison
        return normalize_name(name1) == normalize_name(name2)

    def is_open_access(self, journal_name: str) -> bool:
        """
        Check if journal is Open Access.

        Args:
            journal_name: Any journal name variant

        Returns
        -------
            True if the journal is KNOWN to be OA. False means "not known to
            be OA" -- including when the local cache is absent, which is
            reported loudly rather than silently fetched.
        """
        issn_l = self.get_issn_l(journal_name)
        if issn_l and issn_l in self._issn_l_data:
            return self._issn_l_data[issn_l].get("is_oa", False)
        return False

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for journals by name (prefix/substring match).

        Args:
            query: Search query
            limit: Maximum results

        Returns
        -------
            List of matching journal info dicts
        """
        self._ensure_indexes()

        if not query:
            return []

        norm_query = normalize_name(query)
        results = []

        for norm_name, issn_l in self._name_to_issn_l.items():
            if norm_query in norm_name:
                if issn_l in self._issn_l_data:
                    results.append({"issn_l": issn_l, **self._issn_l_data[issn_l]})
                    if len(results) >= limit:
                        break

        return results

    @property
    def journal_count(self) -> int:
        """Get number of cached journals."""
        self._ensure_indexes()
        return self._journal_count

    @property
    def cache_age_hours(self) -> float:
        """Get cache age in hours."""
        if self._last_updated == 0:
            return float("inf")
        return (time.time() - self._last_updated) / 3600


# ==================== Convenience Functions ====================
def get_journal_normalizer(cache_dir: Optional[Path] = None) -> JournalNormalizer:
    """Get the journal normalizer singleton."""
    return JournalNormalizer.get_instance(cache_dir)


def normalize_journal_name(name: str) -> Optional[str]:
    """Normalize journal name to canonical form."""
    return get_journal_normalizer().normalize(name)


def get_journal_issn_l(name: str) -> Optional[str]:
    """Get ISSN-L for a journal name."""
    return get_journal_normalizer().get_issn_l(name)


def is_same_journal(name1: str, name2: str) -> bool:
    """Check if two names refer to the same journal."""
    return get_journal_normalizer().is_same_journal(name1, name2)


def refresh_journal_cache() -> None:
    """Force refresh the journal normalizer cache. Takes minutes; blocks."""
    get_journal_normalizer().refresh()


# EOF
