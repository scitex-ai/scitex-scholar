#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bioRxiv Search Engine - preprint discovery via the bioRxiv API.

Hub parity (old-direct `search_biorxiv`): the bioRxiv API is
date-based, so the engine lists a recent window and filters by query
substring on title/abstract, capped at `max_results`.

Features:
  - 365-day listing window (hub parity), year filters applied post-API
  - Substring match on title/abstract (hub parity)
  - Standardized paper dicts (the arXiv-engine shape)
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

import scitex_logging as logging

from .._BaseSearchEngine import BaseSearchEngine

logger = logging.getLogger(__name__)


class BioRxivSearchEngine(BaseSearchEngine):
    """bioRxiv search engine for preprint discovery."""

    #: Hub parity: the listing window the old-direct search covers.
    LISTING_WINDOW_DAYS = 365

    #: Hub parity: per-request cap on the old-direct endpoint.
    MAX_RESULTS = 50

    def __init__(self):
        """Initialize the bioRxiv search engine (no key needed)."""
        self._session = None

    @property
    def name(self) -> str:
        return "BioRxiv"

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": "SciTeX/1.0 (mailto:research@example.com)"}
            )
        return self._session

    def search_by_keywords(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search bioRxiv by keywords (substring over a recent listing).

        Args:
            query: Keyword query (matched case-insensitively against
                title and abstract, hub parity)
            filters: Optional filters (year_start, year_end -- applied
                post-API, the arXiv-engine rule)
            max_results: Maximum results (hub cap: 50)

        Returns:
            List of paper metadata dictionaries (the arXiv-engine shape)
        """
        filters = filters or {}
        cap = max(1, min(max_results or 25, self.MAX_RESULTS))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.LISTING_WINDOW_DAYS)
        window = f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"

        logger.info(f"{self.name}: Listing {window} for {query[:50]}...")

        try:
            results = []
            cursor = 0
            total = None
            lowered = query.lower()
            while len(results) < cap:
                url = f"https://api.biorxiv.org/details/biorxiv/{window}/{cursor}"
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                payload = response.json()
                collection = payload.get("collection", [])
                if total is None:
                    messages = payload.get("messages", [])
                    total = messages[0].get("total", 0) if messages else 0
                if not collection:
                    break
                for paper in collection:
                    title = paper.get("title", "") or ""
                    abstract = paper.get("abstract", "") or ""
                    if lowered in title.lower() or lowered in abstract.lower():
                        metadata = self._biorxiv_to_standard_format(paper)
                        if metadata and self._passes_year_filter(metadata, filters):
                            results.append(metadata)
                            if len(results) >= cap:
                                break
                cursor += len(collection)
                if total is not None and cursor >= total:
                    break
            logger.info(f"{self.name}: {len(results)} papers for {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"{self.name}: Search failed: {e}")
            return []

    def _biorxiv_to_standard_format(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a bioRxiv collection entry to the standard shape."""
        title = paper.get("title") or None
        authors_raw = paper.get("authors") or ""
        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
        journal = paper.get("journal") or paper.get("server") or "bioRxiv"
        year = None
        date = paper.get("date") or ""
        if len(date) >= 4 and date[:4].isdigit():
            year = int(date[:4])
        doi = paper.get("doi") or None
        abstract = paper.get("abstract") or None
        return {
            "id": {
                "doi": doi,
                "doi_engines": [self.name] if doi else None,
            },
            "basic": {
                "title": title,
                "title_engines": [self.name] if title else None,
                "authors": authors if authors else None,
                "authors_engines": [self.name] if authors else None,
                "abstract": abstract,
                "abstract_engines": [self.name] if abstract else None,
            },
            "publication": {
                "year": year,
                "year_engines": [self.name] if year else None,
                "journal": journal,
            },
            "urls": {
                "pdf": f"https://www.biorxiv.org/content/{doi}.full.pdf" if doi else None,
                "publisher": f"https://doi.org/{doi}" if doi else None,
            },
        }

    def _passes_year_filter(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """Check if paper passes the year filter (the arXiv-engine rule)."""
        year = metadata.get("publication", {}).get("year")
        if year is None:
            return True
        year_start = filters.get("year_start")
        year_end = filters.get("year_end")
        if year_start and year < year_start:
            return False
        if year_end and year > year_end:
            return False
        return True


# EOF
