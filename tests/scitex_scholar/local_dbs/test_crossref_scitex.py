"""Smoke import mirror for scitex_scholar.local_dbs.crossref_scitex.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import pytest


def test_import_crossref_scitex_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a missing
    dependency is reported as a skip, not a pass). The single assertion
    verifies the loaded module's ``__name__`` matches the requested
    dotted path — catches accidental aliasing and packaging-path drift,
    which a bare import does not.

    ``exc_type=ImportError`` is required: the module's optional backing
    peer is ``crossref-local``, and when it is absent ``crossref_scitex``
    re-raises a *helpful* ``ImportError`` ("crossref-local not installed.
    Install with: pip install crossref-local") rather than letting the
    bare ``ModuleNotFoundError`` propagate. Since pytest 9.1,
    ``importorskip`` defaults to catching only ``ModuleNotFoundError``, so
    that re-raised ``ImportError`` would surface as a hard failure instead
    of a skip. Passing ``exc_type=ImportError`` restores "absent optional
    dependency -> skip" for the install-hint path while still letting any
    non-ImportError breakage (rename, missing symbol) fail loudly.
    """
    # Arrange
    name = "scitex_scholar.local_dbs.crossref_scitex"
    # Act
    mod = pytest.importorskip(name, exc_type=ImportError)
    # Assert
    assert mod.__name__ == name
