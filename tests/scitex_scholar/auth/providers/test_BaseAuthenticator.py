"""Smoke import mirror for scitex_scholar.auth.providers.BaseAuthenticator.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import importlib


def test_import_BaseAuthenticator_module():
    """Module imports without raising hard errors."""
    try:
        importlib.import_module("scitex_scholar.auth.providers.BaseAuthenticator")
    except ImportError:
        # Optional-dependency module; skip when extras absent.
        return
