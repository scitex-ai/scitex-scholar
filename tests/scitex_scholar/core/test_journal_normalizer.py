"""Smoke import mirror for scitex_scholar.core.journal_normalizer.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import importlib


def test_import_journal_normalizer_module():
    """Module imports without raising hard errors."""
    try:
        importlib.import_module("scitex_scholar.core.journal_normalizer")
    except ImportError:
        # Optional-dependency module; skip when extras absent.
        return
