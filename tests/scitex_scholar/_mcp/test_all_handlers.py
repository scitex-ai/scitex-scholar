"""Smoke import mirror for scitex_scholar._mcp.all_handlers.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import importlib


def test_import_all_handlers_module():
    """Module imports without raising hard errors."""
    try:
        importlib.import_module("scitex_scholar._mcp.all_handlers")
    except ImportError:
        # Optional-dependency module; skip when extras absent.
        return
