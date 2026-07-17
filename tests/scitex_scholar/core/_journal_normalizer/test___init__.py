#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the journal normalizer package's public surface."""

from scitex_scholar.core import _journal_normalizer


def test_package_exports_the_normalizer_class():
    # Arrange
    name = "JournalNormalizer"
    # Act
    result = hasattr(_journal_normalizer, name)
    # Assert
    assert result is True


def test_package_exports_the_explicit_refresh_entry_point():
    # Arrange
    name = "refresh_journal_cache"
    # Act
    result = hasattr(_journal_normalizer, name)
    # Assert -- the ONLY sanctioned way to reach the network
    assert result is True


def test_all_matches_the_module_attributes():
    # Arrange
    exported = _journal_normalizer.__all__
    # Act
    missing = [n for n in exported if not hasattr(_journal_normalizer, n)]
    # Assert
    assert missing == []


# EOF
