#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLOS search engine (engine parity, hub old-direct source).

Hub `search_plos`: Solr article search (title/author/journal/date/
abstract), capped rows. CHANGE: a leaf `PLOSSearchEngine` following the
`PubMedSearchEngine` shape (`search_by_keywords` -> standardized
dicts) + ONLINE_ENGINES registration + `plos` alias + Sources-grid
checkbox. VERIFY: pins with offline-stubbed HTTP (no network).
"""

from __future__ import annotations

from scitex_scholar.search_engines import _source_tiers as _tiers
from scitex_scholar.search_engines.individual.PLOSSearchEngine import (
    PLOSSearchEngine,
)


def _doc(**over):
    doc = {
        "id": "10.1371/journal.pone.0123456",
        "title": ["PLOS hippocampus study"],
        "author": ["Doe J", "Smith A"],
        "journal": "PLOS ONE",
        "publication_date": "2023-05-01T00:00:00Z",
        "abstract": ["An open PLOS study of ripples."],
    }
    doc.update(over)
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
    engine = PLOSSearchEngine.__new__(PLOSSearchEngine)
    engine._session = _StubSession(payload)
    return engine


def test_plos_maps_solr_docs_to_standardized_dicts():
    # Arrange
    engine = _engine({"response": {"docs": [_doc()]}})
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=10)
    # Assert -- one tuple compare: envelope + mapped fields.
    assert (
        len(results),
        results[0]["basic"]["title"],
        results[0]["basic"]["authors"],
        results[0]["publication"]["journal"],
        results[0]["publication"]["year"],
        results[0]["id"]["doi"],
        results[0]["metrics"]["is_open_access"],
        results[0]["urls"]["pdf"],
    ) == (
        1,
        "PLOS hippocampus study",
        ["Doe J", "Smith A"],
        "PLOS ONE",
        2023,
        "10.1371/journal.pone.0123456",
        True,
        "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0123456&type=printable",
    )


def test_plos_queries_title_and_abstract_with_year_filter():
    # Arrange
    engine = _engine(
        {"response": {"docs": [_doc(), _doc(publication_date="2020-01-01T00:00:00Z")]}}
    )
    # Act
    results = engine.search_by_keywords(
        "hippocampus", filters={"year_start": 2022}, max_results=50
    )
    # Assert -- Solr title/abstract query shape; old doc filtered post-API.
    (url, params), = engine._session.calls
    assert (
        url,
        "title:" in params["q"],
        "abstract:" in params["q"],
        [r["publication"]["year"] for r in results],
    ) == ("https://api.plos.org/search", True, True, [2023])


def test_plos_failure_returns_empty_never_raises():
    # Arrange
    engine = PLOSSearchEngine.__new__(PLOSSearchEngine)
    engine._session = _FailingSession()
    # Act
    results = engine.search_by_keywords("hippocampus")
    # Assert
    assert results == []


def test_plos_is_registered_and_selectable():
    # Arrange (no Arrange step: static registration inspection)
    # Act
    canonical = _tiers.normalize_sources("plos")
    # Assert -- engine registered, alias resolves.
    assert (
        _tiers.ONLINE_ENGINES.get("PLOS") is PLOSSearchEngine,
        canonical,
    ) == (True, ["PLOS"])
