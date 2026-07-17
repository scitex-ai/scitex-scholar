#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the pure name/ISSN normalization helpers."""

from scitex_scholar.core._journal_normalizer._names import (
    normalize_issn,
    normalize_name,
)


def test_normalize_name_lowercases():
    # Arrange
    name = "Journal Of Neuroscience"
    # Act
    result = normalize_name(name)
    # Assert
    assert result == "journal of neuroscience"


def test_normalize_name_strips_punctuation():
    # Arrange
    name = "J. Neurosci."
    # Act
    result = normalize_name(name)
    # Assert
    assert result == "j neurosci"


def test_normalize_name_collapses_whitespace():
    # Arrange
    name = "PLOS    ONE"
    # Act
    result = normalize_name(name)
    # Assert
    assert result == "plos one"


def test_normalize_name_expands_ampersand():
    # Arrange
    name = "Cell & Tissue"
    # Act
    result = normalize_name(name)
    # Assert
    assert result == "cell and tissue"


def test_normalize_name_handles_empty():
    # Arrange
    name = ""
    # Act
    result = normalize_name(name)
    # Assert
    assert result == ""


def test_normalize_issn_inserts_hyphen():
    # Arrange
    issn = "19326203"
    # Act
    result = normalize_issn(issn)
    # Assert
    assert result == "1932-6203"


def test_normalize_issn_preserves_hyphenated_form():
    # Arrange
    issn = "1932-6203"
    # Act
    result = normalize_issn(issn)
    # Assert
    assert result == "1932-6203"


def test_normalize_issn_uppercases_check_digit():
    # Arrange
    issn = "0000-000x"
    # Act
    result = normalize_issn(issn)
    # Assert
    assert result == "0000-000X"


# EOF
