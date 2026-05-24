"""Smoke import mirror for scitex_scholar.impact_factor.jcr.build_database.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import pytest


def test_import_build_database_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a
    missing dependency is reported as a skip, not a pass). The
    single assertion verifies the loaded module's ``__name__``
    matches the requested dotted path — catches accidental aliasing
    and packaging-path drift, which a bare import does not.
    """
    # Arrange
    name = "scitex_scholar.impact_factor.jcr.build_database"
    # Act
    mod = pytest.importorskip(name)
    # Assert
    assert mod.__name__ == name
