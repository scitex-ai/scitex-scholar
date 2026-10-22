#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOAJ Search Engine - open-access discovery via the DOAJ API v2.

Hub parity (old-direct `search_doaj`): article search over bibjson,
capped results, open-access always true.
"""

from typing import Any, Dict, List, Optional

import requests

import scitex_logging as logging

from .._BaseSearchEngine import BaseSearchEngine

logger = logging.getLogger(__name__)


class DOAJSearchEngine(BaseSearchEngine):
    """DOAJ search engine for open-access article discovery."""

    #: Hub parity: per-request cap on the old-direct endpoint.
    MAX_RESULTS = 50

    def __init__(self):
        """Initialize the DOAJ search engine (no key needed)."""
        self._session = None

    @property
    def name(self) -> str:
        return "DOAJ"

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
        """Search DOAJ articles by keywords.

        Args:
            query: Keyword query (DOAJ scores title/abstract)
            filters: Optional filters (year_start, year_end -- applied
                post-API, the arXiv-engine rule)
            max_results: Maximum results (hub cap: 50)

        Returns:
            List of paper metadata dictionaries (the arXiv-engine shape)
        """
        filters = filters or {}
        cap = max(1, min(max_results or 25, self.MAX_RESULTS))
        logger.info(f"{self.name}: Searching DOAJ for {query[:50]}...")

        try:
            response = self.session.get(
                "https://doaj.org/api/v2/search/articles",
                params={"q": query, "pageSize": cap, "sort": "score:desc"},
                timeout=60,
            )
            response.raise_for_status()
            articles = response.json().get("results", [])[:cap]
            results = []
            for article in articles:
                metadata = self._bibjson_to_standard_format(article.get("bibjson", {}))
                if metadata and self._passes_year_filter(metadata, filters):
                    results.append(metadata)
            logger.info(f"{self.name}: {len(results)} papers for {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"{self.name}: Search failed: {e}")
            return []

    def _bibjson_to_standard_format(self, bibjson: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a DOAJ bibjson record to the standard shape."""
        title = bibjson.get("title") or None
        authors = [
            a.get("name", "").strip()
            for a in bibjson.get("author", [])
            if a.get("name", "").strip()
        ]
        journal = (bibjson.get("journal") or {}).get("title") or "DOAJ Journal"
        year = None
        raw_year = bibjson.get("year")
        if isinstance(raw_year, int):
            year = raw_year
        elif isinstance(raw_year, str) and raw_year[:4].isdigit():
            year = int(raw_year[:4])
        doi = None
        for ident in bibjson.get("identifier", []):
            if ident.get("type") == "doi":
                doi = ident.get("id")
                break
        pdf_url = None
        for link in bibjson.get("link", []):
            if "pdf" in str(link.get("content_type", "")).lower():
                pdf_url = link.get("url")
                break
        abstract = bibjson.get("abstract") or None
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
            "metrics": {
                "is_open_access": True,
            },
            "urls": {
                "pdf": pdf_url,
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
