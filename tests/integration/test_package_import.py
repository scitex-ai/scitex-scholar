#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/integration/test_package_import.py

"""Basic package import smokes.

Rewritten from the legacy ``unittest.TestCase`` shape (which made
``self.assertX`` invisible to STX-TQ001 and packed multiple assertions
per method, violating STX-TQ007). One pytest test ↔ one bare ``assert``
↔ one piece of behaviour now.
"""

from __future__ import annotations

import importlib


def test_scitex_scholar_package_imports_without_error():
    # Arrange
    name = "scitex_scholar"
    # Act
    mod = importlib.import_module(name)
    # Assert
    assert mod.__name__ == name


def test_scitex_scholar_exposes_version_attribute():
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert hasattr(scitex_scholar, "__version__")


def test_scitex_scholar_version_is_a_string():
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert isinstance(scitex_scholar.__version__, str)


def test_scitex_scholar_version_is_non_empty():
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert len(scitex_scholar.__version__) > 0


def test_scitex_scholar_exposes_author_attribute():
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert hasattr(scitex_scholar, "__author__")


def test_scitex_scholar_author_is_yusuke_watanabe():
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert scitex_scholar.__author__ == "Yusuke Watanabe"


def test_scitex_scholar_does_not_expose_email_on_umbrella():
    """SciTeX community packages must not expose `__email__` on the umbrella."""
    # Arrange
    # Act
    import scitex_scholar

    # Assert
    assert not hasattr(scitex_scholar, "__email__")


# EOF
