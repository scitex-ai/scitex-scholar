#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: "2025-10-11 23:58:17 (ywatanabe)"
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/extra/JournalMetrics.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = "./src/scitex/scholar/extra/JournalMetrics.py"
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

__FILE__ = __file__

"""
Functionalities:
- Retrieves journal impact factors and quartiles
- Provides standalone journal metrics lookup
- Caches results for performance optimization

Dependencies:
- packages:
  - impact_factor

Input:
- Journal names as strings

Output:
- Dictionary containing impact factor and quartile data
"""

"""Imports"""
from functools import lru_cache
from typing import Dict, Optional

from scitex_logging import getLogger

from .jcr.ImpactFactorJCREngine import TABLE as JCR_TABLE
from .jcr.ImpactFactorJCREngine import ImpactFactorJCREngine

logger = getLogger(__name__)

"""Parameters"""

"""Functions & Classes"""


class ImpactFactorEngine:
    """
    Impact factor service - finds journal metrics from the JCR table.

    Reads the JCR rows through :class:`ImpactFactorJCREngine`, with an LRU
    cache in front so repeated lookups of the same journal are free.
    """

    def __init__(self, cache_size: int = 1000):
        """Initialize with optional cache size."""
        self.name = self.__class__.__name__
        self.jcr_engine = ImpactFactorJCREngine()
        self.get_metrics = lru_cache(maxsize=cache_size)(self._get_metrics_uncached)

    def _get_jcr_year(self) -> str:
        """Which JCR edition the numbers came from.

        The edition is stamped on every row when the export is loaded, so
        it is read rather than inferred. Returns "Source Unknown" when no
        row carries one -- rows loaded before the field existed, or an
        empty table.
        """
        try:
            year = self.jcr_engine.jcr_year
            if year:
                return f"JCR {year}"
        except Exception as exc:
            logger.debug(
                f"ImpactFactorEngine: JCR year lookup failed "
                f"({type(exc).__name__}: {exc}); returning 'Source Unknown'"
            )

        return "Source Unknown"

    def _get_metrics_uncached(self, journal_name: str) -> Optional[Dict]:
        """Get journal metrics without caching."""
        if not self.jcr_engine or not journal_name:
            return None

        try:
            results = self.jcr_engine.search(journal_name)
            if results:
                result = results[0]
                return {
                    "impact_factor": float(result.get("factor") or 0),
                    "quartile": result.get("jcr", "Unknown"),
                    "source": self._get_jcr_year(),
                }
        except Exception as exc:
            # Logged, not swallowed: "no metrics for this journal" and "the
            # table could not be read at all" are different answers, and the
            # bare `pass` that used to be here made an unreachable store look
            # exactly like an unlisted journal.
            logger.debug(
                f"ImpactFactorEngine: lookup for {journal_name!r} failed "
                f"({type(exc).__name__}: {exc})"
            )

        return None

    def get_database_info(self) -> Dict:
        """Describe where the impact-factor rows live and what is in them."""
        if not self.jcr_engine:
            return {"error": "JCR engine not available"}

        try:
            records = self.jcr_engine.records
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

        info = {
            "store": self.jcr_engine.store,
            "table": JCR_TABLE,
            "total_journals": len(records),
            "data_year": self._get_jcr_year(),
            "columns": sorted(records[0]) if records else [],
            "sample_data": records[:3],
        }
        return info


def get_journal_metrics(journal_name: str) -> Optional[Dict]:
    """Standalone function to get journal metrics.

    Parameters
    ----------
    journal_name : str
        Name of the journal

    Returns
    -------
    Optional[Dict]
        Dictionary with impact_factor, quartile, and source keys

    Example
    -------
    >>> metrics = get_journal_metrics("Nature")
    >>> print(metrics["impact_factor"])
    64.8
    """
    engine = ImpactFactorEngine()
    return engine.get_metrics(journal_name)


if __name__ == "__main__":

    def main():
        """Demonstrate journal metrics lookup."""
        metrics_instance = ImpactFactorEngine()

        # Show where the rows come from
        print("Impact-factor table")
        print("=" * 50)
        db_info = metrics_instance.get_database_info()
        for key, value in db_info.items():
            print(f"{key}: {value}")

        print("\nJournal Metrics Lookup Demo")
        print("=" * 50)

        test_journals = ["Nature", "Science", "Cell"]

        for journal in test_journals:
            print(f"\nJournal: {journal}")
            metrics = get_journal_metrics(journal)
            if metrics:
                for key, value in metrics.items():
                    print(f"  {key}: {value}")
            else:
                print("  No metrics found")

    main()
# python -m scitex_scholar.extra.JournalMetrics

# EOF
