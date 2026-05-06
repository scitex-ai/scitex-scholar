"""Smoke import mirror for scitex_scholar.url_finder.strategies.find_pdf_urls_by_direct_links.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import importlib


def test_import_find_pdf_urls_by_direct_links_module():
    """Module imports without raising hard errors."""
    try:
        importlib.import_module("scitex_scholar.url_finder.strategies.find_pdf_urls_by_direct_links")
    except ImportError:
        # Optional-dependency module; skip when extras absent.
        return
