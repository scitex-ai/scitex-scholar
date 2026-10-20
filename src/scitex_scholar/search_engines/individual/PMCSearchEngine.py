#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PMC Search Engine - open-access discovery via NCBI E-utilities (db=pmc).

Hub parity (old-direct `search_pubmed_central`): esearch over db=pmc
with the open-access filter. Cleaner than hub: hub fills placeholder
titles without fetching metadata; the leaf resolves each ID through
esummary, so results carry real titles/authors/journal/year.
"""

from typing import Any, Dict, List, Optional

import requests

import scitex_logging as logging

from .._BaseSearchEngine import BaseSearchEngine

logger = logging.getLogger(__name__)


class PMCSearchEngine(BaseSearchEngine):
    """PMC search engine for open-access paper discovery."""

    #: Hub parity: per-request cap on the old-direct endpoint.
    MAX_RESULTS = 50

    def __init__(self, email: str = "research@example.com"):
        """Initialize the PMC search engine.

        Args:
            email: Email for NCBI E-utilities (required for polite usage)
        """
        self.email = email
        self._session = None

    @property
    def name(self) -> str:
        return "PMC"

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": f"SciTeX/1.0 (mailto:{self.email})"}
            )
        return self._session

    def search_by_keywords(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search PMC by keywords.

        Args:
            query: Keyword query (NCBI term + open-access filter)
            filters: Optional filters (year_start, year_end -- applied
                post-API, the arXiv-engine rule)
            max_results: Maximum results (hub cap: 50)

        Returns:
            List of paper metadata dictionaries (the arXiv-engine shape)
        """
        filters = filters or {}
        cap = max(1, min(max_results or 25, self.MAX_RESULTS))
        logger.info(f"{self.name}: Searching PMC for {query[:50]}...")

        try:
            response = self.session.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    "db": "pmc",
                    "term": f'{query} AND "open access"[Filter]',
                    "retmax": cap,
                    "retmode": "json",
                    "sort": "relevance",
                    "email": self.email,
                },
                timeout=60,
            )
            response.raise_for_status()
            idlist = response.json().get("esearchresult", {}).get("idlist", [])[:cap]
            if not idlist:
                logger.info(f"{self.name}: No results found")
                return []
            results = []
            for pmc_id in idlist:
                try:
                    metadata = self._summarize(pmc_id)
                except Exception as e:
                    logger.warning(f"{self.name}: esummary failed for {pmc_id}: {e}")
                    continue
                if metadata and self._passes_year_filter(metadata, filters):
                    results.append(metadata)
            logger.info(f"{self.name}: {len(results)} papers for {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"{self.name}: Search failed: {e}")
            return []

    def _summarize(self, pmc_id: str) -> Optional[Dict[str, Any]]:
        """Resolve one PMC ID through esummary to a standard dict."""
        response = self.session.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pmc", "id": pmc_id, "retmode": "json", "email": self.email},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json().get("result", {})
        record = payload.get(str(pmc_id), {})
        if not record:
            return None
        title = record.get("title") or None
        authors = [
            a.get("name", "").strip()
            for a in record.get("authors", [])
            if a.get("name", "").strip()
        ]
        year = None
        pubdate = record.get("pubdate", "") or ""
        if len(pubdate) >= 4 and pubdate[:4].isdigit():
            year = int(pubdate[:4])
        journal = record.get("source") or "PMC Open Access"
        doi = record.get("elocationid") or None
        if doi and not doi.startswith("10."):
            doi = None
        return {
            "id": {
                "pmc": f"PMC{pmc_id}",
                "doi": doi,
                "doi_engines": [self.name] if doi else None,
            },
            "basic": {
                "title": title,
                "title_engines": [self.name] if title else None,
                "authors": authors if authors else None,
                "authors_engines": [self.name] if authors else None,
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
                "pdf": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                "publisher": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/",
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
