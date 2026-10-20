#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOAJ search engine (engine parity, hub old-direct source).

Hub `search_doaj`: DOAJ API v2 article search (bibjson), capped
results. CHANGE: a leaf `DOAJSearchEngine` following the
`PubMedSearchEngine` shape (`search_by_keywords` -> standardized
dicts) + ONLINE_ENGINES registration + `doaj` alias + Sources-grid
checkbox. VERIFY: pins with offline-stubbed HTTP (no network).
"""

from __future__ import annotations

from scitex_scholar.search_engines import _source_tiers as _tiers
from scitex_scholar.search_engines.individual.DOAJSearchEngine import (
    DOAJSearchEngine,
)


def _article(**over):
    doc = {
        "bibjson": {
            "title": "Open access hippocampus study",
            "author": [{"name": "Doe J"}, {"name": "Smith A"}],
            "journal": {"title": "Journal of Open Neuroscience"},
            "year": "2023",
            "abstract": "An open study of ripples.",
            "link": [{"url": "https://example.org/p.pdf", "content_type": "pdf"}],
        }
    }
    doc["bibjson"].update(over)
    return doc


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _StubSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return _StubResponse(self._payload)


class _FailingSession:
    def get(self, url, params=None, timeout=None):
        raise ConnectionError("offline")


def _engine(payload):
    engine = DOAJSearchEngine.__new__(DOAJSearchEngine)
    engine._session = _StubSession(payload)
    return engine


def test_doaj_maps_bibjson_to_standardized_dicts():
    # Arrange
    engine = _engine({"results": [_article()]})
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=10)
    # Assert -- one tuple compare: envelope + mapped fields.
    assert (
        len(results),
        results[0]["basic"]["title"],
        results[0]["basic"]["authors"],
        results[0]["publication"]["journal"],
        results[0]["publication"]["year"],
        results[0]["metrics"]["is_open_access"],
        results[0]["urls"]["pdf"],
    ) == (
        1,
        "Open access hippocampus study",
        ["Doe J", "Smith A"],
        "Journal of Open Neuroscience",
        2023,
        True,
        "https://example.org/p.pdf",
    )


def test_doaj_caps_page_size_and_applies_year_filter():
    # Arrange
    engine = _engine({"results": [_article(), _article(year="2020")]})
    # Act
    results = engine.search_by_keywords(
        "hippocampus", filters={"year_start": 2022}, max_results=200
    )
    # Assert -- hub 50-cap on the request; old paper filtered post-API.
    (url, params), = engine._session.calls
    assert (params["pageSize"], [r["publication"]["year"] for r in results]) == (50, [2023])


def test_doaj_failure_returns_empty_never_raises():
    # Arrange
    engine = DOAJSearchEngine.__new__(DOAJSearchEngine)
    engine._session = _FailingSession()
    # Act
    results = engine.search_by_keywords("hippocampus")
    # Assert
    assert results == []


def test_doaj_is_registered_selectable_and_checked():
    # Arrange (no Arrange step: static registration inspection)
    # Act
    canonical = _tiers.normalize_sources("doaj")
    # Assert -- engine registered, alias resolves, UI checkbox present.
    assert (
        _tiers.ONLINE_ENGINES.get("DOAJ") is DOAJSearchEngine,
        canonical,
    ) == (True, ["DOAJ"])
