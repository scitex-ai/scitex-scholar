#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: "2025-10-12 07:17:04 (ywatanabe)"
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/impact_factor/jcr/build_database.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = "./src/scitex/scholar/impact_factor/jcr/build_database.py"
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

"""
Functionalities:
  - Load a JCR Excel export into the shared store
  - Parse JCR Excel exports
  - Extract impact factors and quartiles

Dependencies:
  - packages:
    - openpyxl

IO:
  - input-files:
    - a JCR Excel export (JCR_IF_YYYY.xlsx), supplied by the user
  - output: the ``scholar_impact_factor`` table in the shared store
"""

"""Imports"""
import argparse
import re
from pathlib import Path
from typing import Dict, Iterator, Optional

import openpyxl
import scitex_logging as logging

logger = logging.getLogger(__name__)

# `import scitex as stx` is moved into the demo trailer (run_main) to
# keep module-import umbrella-free per PA304.

"""Parameters"""
"""Functions & Classes"""


def parse_jcr_excel(excel_path: Path) -> Iterator[Dict]:
    """
    Parse JCR Excel file and yield journal records.

    Args:
        excel_path: Path to JCR Excel file

    Yields:
        Dictionary with journal data (journal, factor, issn, etc.)
    """
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    for values in ws.values:
        if values[0] is None:
            continue
        if values[0] in ("Journal Name", "Name"):
            title = [v.upper() for v in values]
            continue

        context = dict(zip(title, values))
        data = {}
        raw_factor = context.get("2021 JIF") or context.get("JIF")
        data["factor"] = _parse_impact_factor(raw_factor)
        data["issn"] = context["ISSN"] if context["ISSN"] != "N/A" else ""
        data["eissn"] = context["EISSN"] if context["EISSN"] != "N/A" else ""
        data["jcr"] = _get_jcr_quartile(context["CATEGORY"])
        data["journal"] = context.get("JOURNAL NAME") or context.get("NAME")

        yield data


def _get_jcr_quartile(category: str) -> str:
    """Extract JCR quartile from category string."""
    res = re.findall(r"[|(](Q\d)[)|]", category)
    return res[0] if res else ""


def _parse_impact_factor(factor_str) -> Optional[float]:
    """
    Parse impact factor string to float.

    Handles special cases like '<0.1', '>100', 'N/A', None, etc.

    Args:
        factor_str: Impact factor value from Excel (can be str, float, or None)

    Returns:
        Float value or None if cannot be parsed
    """
    if factor_str is None or factor_str == "N/A":
        return None

    # Already a float
    if isinstance(factor_str, (int, float)):
        return float(factor_str)

    # Convert to string and clean
    factor_str = str(factor_str).strip()

    if not factor_str or factor_str == "N/A":
        return None

    # Handle '<0.1' -> 0.1
    if factor_str.startswith("<"):
        try:
            return float(factor_str[1:])
        except ValueError:
            logger.warning(f"Could not parse factor value: {factor_str}")
            return None

    # Handle '>100' -> 100
    if factor_str.startswith(">"):
        try:
            return float(factor_str[1:])
        except ValueError:
            logger.warning(f"Could not parse factor value: {factor_str}")
            return None

    # Try direct conversion
    try:
        return float(factor_str)
    except ValueError:
        logger.warning(f"Could not parse factor value: {factor_str}")
        return None


def jcr_year_of(excel_path: Path) -> str:
    """The JCR edition an export belongs to, read from its filename.

    Stored on every row so a later reader can say WHICH edition a number
    came from. The previous code re-derived this from the database
    filename at read time, which meant renaming the file changed the
    reported year while the numbers stayed the same.
    """
    year = re.search(r"20\d{2}", excel_path.name)
    return year.group() if year else "unknown"


def build_database(excel_path: Path, jcr_year: Optional[str] = None) -> int:
    """Load a JCR Excel export into the shared store. Returns row count.

    Rows are UPSERTED by journal title, so re-running with a newer export
    updates the numbers in place and leaves journals absent from the new
    export untouched rather than deleting them.
    """
    from scitex_dev.store import ANY_REVISION

    from .ImpactFactorJCREngine import open_store, store_target

    year = jcr_year or jcr_year_of(excel_path)
    logger.info(f"Loading {excel_path} (JCR {year})")
    logger.info(f"Into: {store_target().locator}")

    count = 0
    store = open_store()
    try:
        with store.batch():
            for record in parse_jcr_excel(excel_path):
                journal = record.get("journal")
                if not journal:
                    continue
                store.put(
                    {
                        "journal": journal,
                        "journal_abbr": record.get("journal_abbr"),
                        "issn": record.get("issn"),
                        "eissn": record.get("eissn"),
                        "nlm_id": record.get("nlm_id"),
                        "factor": record.get("factor"),
                        "jcr": record.get("jcr"),
                        "jcr_year": year,
                    },
                    expected_revision=ANY_REVISION,
                )
                count += 1
                if count % 100 == 0:
                    logger.info(f"Processed {count} journals...")
    finally:
        store.close()

    logger.success(f"Loaded {count} journals (JCR {year})")
    return count


def main(args):
    """Main function to load the JCR export into the store."""
    excel_path = Path(args.excel)

    if not excel_path.exists():
        logger.error(f"Excel file not found: {excel_path}")
        return 1

    try:
        count = build_database(excel_path, args.jcr_year)
        logger.success(f"{count} journals loaded")
        return 0
    except Exception as e:
        logger.error(f"Failed to load JCR export: {e}")
        return 1


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Load a JCR Excel export into the scholar store"
    )
    parser.add_argument(
        "--excel",
        "-e",
        type=str,
        required=True,
        help="Path to JCR Excel file (e.g., JCR_IF_2021.xlsx)",
    )
    parser.add_argument(
        "--jcr-year",
        type=str,
        default=None,
        help="JCR edition to stamp on every row (read from the filename if omitted)",
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
python -m scitex_scholar.impact_factor.jcr.build_database \
    -e ~/Downloads/JCR_IF_2024.xlsx
"""

# EOF
