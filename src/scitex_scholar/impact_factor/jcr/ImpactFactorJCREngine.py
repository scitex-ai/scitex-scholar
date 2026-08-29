#!/usr/bin/env python3
# File: src/scitex_scholar/impact_factor/jcr/ImpactFactorJCREngine.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = __file__
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

"""
Functionalities:
  - Query the JCR journal table for impact factors
  - Returns impact factor, quartile, ISSN information
  - Handles missing data gracefully

IO:
  - input: the ``scholar_impact_factor`` table in the shared store
    (:mod:`scitex_dev.store`), populated by ``build_database.py``
  - output: none (read-only queries)

WHY THE ROWS LIVE IN THE STORE
------------------------------
The JCR table is DERIVED STATE that scholar owns: a user's JCR Excel export
turned into rows. It used to live in a file whose location three modules
described three different ways, and whose default resolved OUTSIDE the
repository after the monorepo split -- so every lookup failed, silently,
for anyone who did not pass a path by hand. There is no path here any more:
``host_store()`` resolves WHERE, and a store that cannot be reached raises
naming the target instead of quietly answering "journal not found".
"""

"""Imports"""
import argparse
import socket
from typing import Dict, List, Optional

import scitex_logging as logging

logger = logging.getLogger(__name__)

"""Parameters"""
STORE_NAME = "impact_factor"
TABLE = "scholar_impact_factor"

SEARCH_KEYS = ["issn", "eissn", "nlm_id", "journal", "journal_abbr"]

"""Functions & Classes"""


def schema():
    """Build the JCR table's :class:`~scitex_dev.store.Schema`.

    ``journal`` is the identity because JCR keys its export by journal
    title, and ``IMMUTABLE`` because renaming a journal produces a new row
    rather than silently rewriting the old one's history.
    """
    from scitex_dev.store import FieldKind, FieldPolicy, FieldRole, MergeRule, Schema

    def ident(kind):
        return FieldPolicy(
            kind=kind,
            role=FieldRole.IDENTITY,
            required=True,
            merge=MergeRule.IMMUTABLE,
            indexed=False,
        )

    def data(kind, *, indexed: bool = False):
        return FieldPolicy(
            kind=kind,
            role=FieldRole.DATA,
            required=False,
            merge=MergeRule.LAST_WRITER_WINS,
            indexed=indexed,
        )

    text = FieldKind.TEXT
    real = FieldKind.REAL

    return Schema.build(
        TABLE,
        {
            "journal": ident(text),
            "journal_abbr": data(text, indexed=True),
            "issn": data(text, indexed=True),
            "eissn": data(text, indexed=True),
            "nlm_id": data(text, indexed=True),
            "factor": data(real),
            "jcr": data(text),
            "jcr_year": data(text),
        },
    )


def store_target():
    """Resolve WHERE the JCR rows live. Pure -- does not connect."""
    from scitex_dev.store import host_store

    return host_store(pkg="scitex_scholar", name=STORE_NAME)


def open_store():
    """Open the JCR store. Raises naming the target if it is unreachable."""
    from scitex_dev.store import Store, WriterPolicy

    return Store(
        store_target(),
        schema(),
        node=socket.gethostname(),
        writer_policy=WriterPolicy.MULTI_WRITER,
        actor="scitex_scholar.impact_factor",
    )


def record_to_dict(values) -> Dict:
    """Normalise one stored row into the shape every caller expects."""
    return {
        "journal": values.get("journal"),
        "journal_abbr": values.get("journal_abbr"),
        "issn": values.get("issn"),
        "eissn": values.get("eissn"),
        "factor": values.get("factor"),
        "jcr": values.get("jcr"),
        "nlm_id": values.get("nlm_id"),
        "jcr_year": values.get("jcr_year"),
    }


class ImpactFactorJCREngine:
    """JCR journal-metrics lookup over the shared store.

    Rows are read ONCE, on first query, and held in memory for the life of
    the engine. That is deliberate: the store exposes lookup by identity and
    a full scan, and four of the five searchable fields are not the identity,
    so a per-query scan would re-read the whole table five times per paper.
    The table is a JCR annual export -- tens of thousands of rows, static
    between releases -- so one read is the right shape.
    """

    def __init__(self, dbfile=None):
        """Initialize the engine.

        ``dbfile`` is accepted and IGNORED. It named a file, and there is no
        file; it stays in the signature only so existing call sites keep
        working across this change, and should be dropped in a follow-up.
        """
        self._records: Optional[List[Dict]] = None

    @property
    def store(self) -> str:
        """Human-readable name of where the rows are read from."""
        return str(store_target().locator)

    @property
    def records(self) -> List[Dict]:
        """Every JCR row, read once and cached on the instance."""
        if self._records is None:
            store = open_store()
            try:
                self._records = [record_to_dict(row.values) for row in store.rows()]
            finally:
                store.close()
        return self._records

    @property
    def jcr_year(self) -> Optional[str]:
        """The JCR edition these rows came from, or None if unrecorded."""
        for record in self.records:
            if record.get("jcr_year"):
                return str(record["jcr_year"])
        return None

    def search(self, value: str, key: Optional[str] = None) -> List[Dict]:
        """Search for a journal.

        Args:
            value: Search value (journal name, ISSN, ...). A ``%`` anywhere
                in the value makes it a wildcard pattern.
            key: Specific field to search (None tries every field in turn).

        Returns
        -------
            List of matching journal records as dictionaries.
        """
        if not value:
            return []
        keys = [key] if key else SEARCH_KEYS

        if "%" in value:
            import fnmatch

            pattern = value.replace("%", "*").lower()

            def matches(field_value) -> bool:
                return field_value is not None and fnmatch.fnmatch(
                    str(field_value).lower(), pattern
                )

        else:
            wanted = value.lower()

            def matches(field_value) -> bool:
                return field_value is not None and str(field_value).lower() == wanted

        for field in keys:
            hits = [r for r in self.records if matches(r.get(field))]
            if hits:
                return hits
        return []

    def filter(self, min_value=None, max_value=None, limit=None) -> List[Dict]:
        """Filter journals by impact factor range."""
        hits = []
        for record in self.records:
            factor = record.get("factor")
            if factor is None:
                continue
            if min_value is not None and factor < min_value:
                continue
            if max_value is not None and factor > max_value:
                continue
            hits.append(record)
        if limit:
            return hits[:limit]
        return hits


def main(args):
    """Main function for CLI usage."""
    engine = ImpactFactorJCREngine()

    if args.search:
        results = engine.search(args.search, args.key)
        if results:
            logger.info(f"Found {len(results)} result(s):")
            for result in results:
                logger.info(f"  Journal: {result['journal']}")
                logger.info(f"  Factor: {result['factor']}")
                logger.info(f"  JCR: {result['jcr']}")
                logger.info(f"  ISSN: {result['issn']}")
                logger.info(f"  eISSN: {result['eissn']}")
                logger.info("")
        else:
            logger.warning(f"No results found for: {args.search}")
        return 0

    if args.filter:
        results = engine.filter(
            min_value=args.min_factor,
            max_value=args.max_factor,
            limit=args.limit,
        )
        logger.info(f"Found {len(results)} journal(s)")
        for result in results[:10]:  # Show first 10
            logger.info(f"  {result['journal']}: {result['factor']}")
        if len(results) > 10:
            logger.info(f"  ... and {len(results) - 10} more")
        return 0

    logger.error("No action specified. Use --search or --filter")
    return 1


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Query JCR journal metrics for impact factors"
    )
    parser.add_argument(
        "--search",
        "-s",
        type=str,
        default=None,
        help="Search for journal by name, ISSN, or other fields",
    )
    parser.add_argument(
        "--key",
        "-k",
        type=str,
        default=None,
        choices=SEARCH_KEYS,
        help="Specific field to search (default: all fields)",
    )
    parser.add_argument(
        "--filter",
        "-f",
        action="store_true",
        default=False,
        help="Filter journals by impact factor range",
    )
    parser.add_argument(
        "--min-factor",
        type=float,
        default=None,
        help="Minimum impact factor for filtering",
    )
    parser.add_argument(
        "--max-factor",
        type=float,
        default=None,
        help="Maximum impact factor for filtering",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Maximum number of results",
    )
    args = parser.parse_args()
    return args


def run_main() -> None:
    """Initialize scitex framework, run main function, and cleanup."""
    global CONFIG, CC, sys, plt, rng

    import sys

    import matplotlib.pyplot as plt
    import scitex_session as session  # peer-standalone session lifecycle

    args = parse_args()

    CONFIG, sys.stdout, sys.stderr, plt, CC, rng = session.start(
        sys,
        plt,
        args=args,
        file=__FILE__,
        sdir_suffix=None,
        verbose=False,
        agg=True,
    )

    exit_status = main(args)

    session.close(
        CONFIG,
        verbose=False,
        notify=False,
        message="",
        exit_status=exit_status,
    )


if __name__ == "__main__":
    run_main()


"""
Examples:

# Search for a specific journal
python -m scitex_scholar.impact_factor.jcr.ImpactFactorJCREngine \
    --search "Nature"

# Search by ISSN
python -m scitex_scholar.impact_factor.jcr.ImpactFactorJCREngine \
    --search "0028-0836" --key issn

# Filter journals by impact factor range
python -m scitex_scholar.impact_factor.jcr.ImpactFactorJCREngine \
    --filter --min-factor 10.0 --max-factor 50.0 --limit 20
"""

# EOF
