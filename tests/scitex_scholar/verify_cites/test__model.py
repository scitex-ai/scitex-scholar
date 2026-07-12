#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__model.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._model (clew boundary mapping)."""
from __future__ import annotations

import pytest

vc_model = pytest.importorskip("scitex_scholar.verify_cites._model")
from scitex_scholar.verify_cites._model import (  # noqa: E402
    HALLUCINATED,
    UNVERIFIED,
    VERIFIED,
    CiteStatus,
)


def test_to_clew_emits_cite_key_kwarg():
    # Arrange
    st = CiteStatus(key="H", status=HALLUCINATED, doi=None)
    # Act
    payload = st.to_clew()
    # Assert
    assert payload["cite_key"] == "H"


def test_to_clew_hallucinated_sets_is_stub_true():
    # Arrange
    st = CiteStatus(key="H", status=HALLUCINATED, doi=None)
    # Act
    payload = st.to_clew()
    # Assert
    assert payload["is_stub"] is True


def test_to_clew_hallucinated_is_not_resolved():
    # Arrange
    st = CiteStatus(key="H", status=HALLUCINATED, doi=None)
    # Act
    payload = st.to_clew()
    # Assert
    assert payload["resolved"] is False


def test_to_clew_verified_is_resolved_and_not_stub():
    # Arrange
    st = CiteStatus(key="V", status=VERIFIED, doi="10.1/x")
    # Act
    payload = st.to_clew()
    # Assert
    assert (payload["resolved"], payload["is_stub"], payload["doi"]) == (True, False, "10.1/x")


def test_to_clew_carries_local_status_in_metadata():
    # Arrange
    st = CiteStatus(key="U", status=UNVERIFIED, doi="10.1/x")
    # Act
    payload = st.to_clew()
    # Assert
    assert payload["metadata"]["local_status"] == UNVERIFIED


def test_to_clew_has_no_status_kwarg():
    # Arrange: clew.add_citation derives status; it must not receive status=.
    st = CiteStatus(key="V", status=VERIFIED, doi="10.1/x")
    # Act
    payload = st.to_clew()
    # Assert
    assert "status" not in payload


def test_to_dict_round_trips_key_and_status():
    # Arrange
    st = CiteStatus(key="V", status=VERIFIED, doi="10.1/x")
    # Act
    d = st.to_dict()
    # Assert
    assert (d["key"], d["status"], d["doi"]) == ("V", VERIFIED, "10.1/x")

# EOF
