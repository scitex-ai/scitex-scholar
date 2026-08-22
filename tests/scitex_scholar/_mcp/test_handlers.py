"""Tests for scitex_scholar._mcp.handlers.

Covers ``_get_scholar_dir()``, which every handler that touches on-disk
state calls before doing anything else.

REGRESSION CONTEXT. The helper resolved the directory as
``ScholarConfig().path_manager.dirs["scholar_dir"]``, but that key does not
exist on the path manager -- only the ``.scholar_dir`` attribute does. Every
call raised ``KeyError: 'scholar_dir'``, and the helper has nine call sites
in that module, so the whole on-disk half of the MCP surface was
unreachable. The identical line had already been corrected in
``gui/_app.py`` by the verify-cites fix; this copy was missed because the
module had no test mirror at all.
"""

from pathlib import Path

import pytest


def test_get_scholar_dir_returns_a_path_instead_of_raising_keyerror():
    """The helper resolves at all -- this is the failing call, pinned."""
    # Arrange
    from scitex_scholar._mcp.handlers import _get_scholar_dir

    # Act
    resolved = _get_scholar_dir()

    # Assert
    assert isinstance(resolved, Path)


def test_get_scholar_dir_returns_an_absolute_path():
    """Callers join filenames onto it, so a relative path would resolve
    against the process CWD and silently write to the wrong place."""
    # Arrange
    from scitex_scholar._mcp.handlers import _get_scholar_dir

    # Act
    resolved = _get_scholar_dir()

    # Assert
    assert resolved.is_absolute()


def test_get_scholar_dir_creates_the_directory_it_returns():
    """The helper promises ``mkdir(parents=True, exist_ok=True)``; a path
    that does not exist would fail every caller at write time instead."""
    # Arrange
    from scitex_scholar._mcp.handlers import _get_scholar_dir

    # Act
    resolved = _get_scholar_dir()

    # Assert
    assert resolved.is_dir()


def test_path_manager_exposes_scholar_dir_as_an_attribute():
    """Pins the supported spelling, so a refactor that drops the attribute
    fails here rather than nine call sites away."""
    # Arrange
    from scitex_scholar.config import ScholarConfig

    path_manager = ScholarConfig().path_manager

    # Act
    scholar_dir = path_manager.scholar_dir

    # Assert
    assert isinstance(scholar_dir, Path)


def test_path_manager_dirs_mapping_has_no_scholar_dir_key():
    """POSITIVE CONTROL for the regression above.

    Without this, a future refactor that reintroduced a ``scholar_dir`` key
    would let the broken spelling start working again -- the tests above
    would still pass, and they would have stopped protecting anything. This
    pins the actual shape of the contract, not only the symptom.
    """
    # Arrange
    from scitex_scholar.config import ScholarConfig

    dirs = ScholarConfig().path_manager.dirs

    # Act / (the lookup under test is the raising expression below)
    # Assert
    with pytest.raises(KeyError):
        dirs["scholar_dir"]


# EOF
