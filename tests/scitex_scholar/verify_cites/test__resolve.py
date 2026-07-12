#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__resolve.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._resolve."""
from __future__ import annotations

import pytest

vc_resolve = pytest.importorskip("scitex_scholar.verify_cites._resolve")
from scitex_scholar.verify_cites._resolve import (  # noqa: E402
    ResolvedRef,
    _authors_list,
    _std,
    default_resolver,
)


def test_authors_list_splits_on_and():
    # Arrange
    raw = "Jane Doe and John Smith and A. B. Carter"
    # Act
    authors = _authors_list({"author": raw})
    # Assert
    assert authors == ["Jane Doe", "John Smith", "A. B. Carter"]


def test_authors_list_empty_without_author_field():
    # Arrange
    # Act
    authors = _authors_list({})
    # Assert
    assert authors == []


def test_std_returns_none_for_empty_metadata():
    # Arrange
    # Act
    resolved = _std(None, "crossref")
    # Assert
    assert resolved is None


def test_std_prefers_top_level_doi():
    # Arrange
    meta = {"title": "T", "doi": "10.1/x"}
    # Act
    resolved = _std(meta, "crossref")
    # Assert
    assert resolved == ResolvedRef(title="T", doi="10.1/x", source="crossref")


def test_std_falls_back_to_external_ids_doi():
    # Arrange
    meta = {"title": "T", "externalIds": {"DOI": "10.1/y"}}
    # Act
    resolved = _std(meta, "semantic_scholar")
    # Assert
    assert resolved.doi == "10.1/y"


def test_default_resolver_offline_short_circuits_without_network():
    # Arrange
    entry = {"title": "Anything", "doi": "10.1/x"}
    # Act
    resolved = default_resolver(entry, offline=True)
    # Assert
    assert resolved is None

# EOF
