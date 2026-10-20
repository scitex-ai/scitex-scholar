#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLOS Search Engine - open-access discovery via the PLOS Solr API.

Hub parity (old-direct `search_plos`): title/abstract Solr query,
capped rows, open-access always true.
"""

from typing import Any, Dict, List, Optional

import requests

import scitex_logging as logging

from .._BaseSearchEngine import BaseSearchEngine

logger = logging.getLogger(__name__)


class PLOSSearchEngine(BaseSearchEngine):
    """PLOS search engine for open-access article discovery."""

    #: Hub parity: per-request cap on the old-direct endpoint.
    MAX_RESULTS = 50

    def __init__(self):
        """Initialize the PLOS search engine (no key needed)."""
        self._session = None

    @property
    def name(self) -> str:
        return "PLOS"

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
        """Search PLOS articles by keywords.

        Args:
            query: Keyword query (Solr title/abstract match)
            filters: Optional filters (year_start, year_end -- applied
                post-API, the arXiv-engine rule)
            max_results: Maximum results (hub cap: 50)

        Returns:
            List of paper metadata dictionaries (the arXiv-engine shape)
        """
        filters = filters or {}
        cap = max(1, min(max_results or 25, self.MAX_RESULTS))
        logger.info(f"{self.name}: Searching PLOS for {query[:50]}...")

        try:
            response = self.session.get(
                "https://api.plos.org/search",
                params={
                    "q": f'title:"{query}" OR abstract:"{query}"',
                    "wt": "json",
                    "rows": cap,
                    "sort": "score desc",
                    "fl": "id,title,author,journal,publication_date,abstract",
                },
                timeout=60,
            )
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs", [])[:cap]
            results = []
            for doc in docs:
                metadata = self._solr_doc_to_standard_format(doc)
                if metadata and self._passes_year_filter(metadata, filters):
                    results.append(metadata)
            logger.info(f"{self.name}: {len(results)} papers for {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"{self.name}: Search failed: {e}")
            return []

    @staticmethod
    def _first(value):
        """Solr fields arrive as single-element lists; unwrap them."""
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _solr_doc_to_standard_format(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a PLOS Solr doc to the standard shape."""
        title = self._first(doc.get("title")) or None
        authors_raw = doc.get("author", [])
        if isinstance(authors_raw, str):
            authors_raw = [authors_raw]
        authors = [a.strip() for a in authors_raw if a and a.strip()]
        journal = doc.get("journal") or "PLOS Journal"
        year = None
        pub_date = doc.get("publication_date", "") or ""
        if len(pub_date) >= 4 and pub_date[:4].isdigit():
            year = int(pub_date[:4])
        doi = doc.get("id") or None
        abstract = self._first(doc.get("abstract")) or None
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
                "pdf": (
                    "https://journals.plos.org/plosone/article/file"
                    f"?id={doi}&type=printable"
                    if doi
                    else None
                ),
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
