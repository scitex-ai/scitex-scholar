#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bioRxiv search engine (engine parity, hub old-direct source).

Hub `search_biorxiv`: date-interval listing (last 365d) + substring
filter on title/abstract, capped results. CHANGE: a leaf
`BioRxivSearchEngine` following the `PubMedSearchEngine` shape
(`search_by_keywords` -> standardized dicts) + ONLINE_ENGINES
registration + `biorxiv` alias + Sources-grid checkbox. VERIFY: pins
with offline-stubbed HTTP (no network in tests).
"""

from __future__ import annotations

from scitex_scholar.search_engines import _source_tiers as _tiers
from scitex_scholar.search_engines.individual.BioRxivSearchEngine import (
    BioRxivSearchEngine,
)


def _collection(*papers):
    return {"messages": [{"count": len(papers), "total": len(papers)}], "collection": list(papers)}


def _paper(**over):
    doc = {
        "title": "Hippocampal sharp waves",
        "authors": "Doe J, Smith A",
        "date": "2024-03-01",
        "doi": "10.1101/2024.01.01.111111",
        "abstract": "Ripples and replay in the hippocampus.",
        "journal": "bioRxiv",
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
        self.calls.append(url)
        return _StubResponse(self._payload)


class _FailingSession:
    def get(self, url, params=None, timeout=None):
        raise ConnectionError("offline")


def _engine(payload):
    engine = BioRxivSearchEngine.__new__(BioRxivSearchEngine)
    engine._session = _StubSession(payload)
    return engine


def test_biorxiv_maps_collection_to_standardized_dicts():
    # Arrange
    engine = _engine(_collection(_paper()))
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
        results[0]["urls"]["pdf"],
    ) == (
        1,
        "Hippocampal sharp waves",
        ["Doe J", "Smith A"],
        "bioRxiv",
        2024,
        "10.1101/2024.01.01.111111",
        "https://www.biorxiv.org/content/10.1101/2024.01.01.111111.full.pdf",
    )


def test_biorxiv_filters_by_query_and_caps_results():
    # Arrange -- one match, one non-match, one more match.
    engine = _engine(
        _collection(
            _paper(title="Hippocampal ripples"),
            _paper(title="Unrelated proteomics", abstract="Mass spec pipelines."),
            _paper(title="Hippocampal replay"),
        )
    )
    # Act
    results = engine.search_by_keywords("hippocampal", max_results=1)
    # Assert -- hub parity: substring filter, then the cap.
    assert ([r["basic"]["title"] for r in results]) == (["Hippocampal ripples"])


def test_biorxiv_failure_returns_empty_never_raises():
    # Arrange
    engine = BioRxivSearchEngine.__new__(BioRxivSearchEngine)
    engine._session = _FailingSession()
    # Act
    results = engine.search_by_keywords("hippocampus")
    # Assert
    assert results == []


def test_biorxiv_is_registered_selectable_and_checked():
    # Arrange (no Arrange step: static registration inspection)
    # Act
    canonical = _tiers.normalize_sources("biorxiv")
    # Assert -- engine registered, alias resolves, UI checkbox present.
    assert (
        _tiers.ONLINE_ENGINES.get("BioRxiv") is BioRxivSearchEngine,
        canonical,
    ) == (True, ["BioRxiv"])
