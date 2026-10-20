#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PMC search engine (engine parity, hub old-direct source).

Hub `search_pubmed_central`: NCBI esearch over db=pmc with the
open-access filter. CHANGE, deliberately cleaner than hub: hub fills
placeholder titles ("PMC Open Access Paper N") without fetching
metadata -- the leaf resolves each ID through esummary, so results
carry real titles/authors/journal/year (implement CLEAN, never port
hub dirt). Shape follows `PubMedSearchEngine` + offline-stubbed pins.
"""

from __future__ import annotations

from scitex_scholar.search_engines import _source_tiers as _tiers
from scitex_scholar.search_engines.individual.PMCSearchEngine import (
    PMCSearchEngine,
)


def _esearch(*ids):
    return {"esearchresult": {"idlist": list(ids), "count": str(len(ids))}}


def _esummary(uid, **over):
    doc = {
        "title": "PMC hippocampus paper",
        "authors": [{"name": "Doe J"}, {"name": "Smith A"}],
        "pubdate": "2023 Jan 5",
        "source": "Frontiers in Testing",
        "volume": "14",
        "elocationid": "10.1234/test",
    }
    doc.update(over)
    return {"result": {"uids": [uid], uid: doc}}


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _StubSession:
    def __init__(self, script):
        self._script = script
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        kind, payload = self._script.pop(0)
        assert kind in url, f"unexpected call order: {url}"
        return _StubResponse(payload)


class _FailingSession:
    def get(self, url, params=None, timeout=None):
        raise ConnectionError("offline")


def test_pmc_resolves_ids_to_real_metadata():
    # Arrange -- esearch IDs, then one esummary payload.
    engine = PMCSearchEngine()
    engine._session = _StubSession(
        [
            ("esearch", _esearch("123", "456")),
            ("esummary", _esummary("123")),
            ("esummary", _esummary("456", title="Second paper", pubdate="2021")),
        ]
    )
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=10)
    # Assert -- real titles/authors/journal/year, not placeholders.
    assert (
        [r["basic"]["title"] for r in results],
        results[0]["basic"]["authors"],
        results[0]["publication"]["journal"],
        [r["publication"]["year"] for r in results],
        results[0]["metrics"]["is_open_access"],
        results[0]["urls"]["pdf"],
    ) == (
        ["PMC hippocampus paper", "Second paper"],
        ["Doe J", "Smith A"],
        "Frontiers in Testing",
        [2023, 2021],
        True,
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/pdf/",
    )


def test_pmc_caps_ids_and_applies_year_filter():
    # Arrange
    engine = PMCSearchEngine()
    engine._session = _StubSession(
        [
            ("esearch", _esearch("1", "2", "3")),
            ("esummary", _esummary("1")),
            ("esummary", _esummary("2", pubdate="2019")),
            ("esummary", _esummary("3", pubdate="2024")),
        ]
    )
    # Act
    results = engine.search_by_keywords(
        "hippocampus", filters={"year_start": 2022}, max_results=2
    )
    # Assert -- esearch capped at max_results; old record filtered.
    (esearch_url, esearch_params), *_ = engine._session.calls
    assert (esearch_params["retmax"], [r["publication"]["year"] for r in results]) == (2, [2023])


def test_pmc_failure_returns_empty_never_raises():
    # Arrange
    engine = PMCSearchEngine()
    engine._session = _FailingSession()
    # Act
    results = engine.search_by_keywords("hippocampus")
    # Assert
    assert results == []


def test_pmc_is_registered_and_selectable():
    # Arrange (no Arrange step: static registration inspection)
    # Act
    canonical = _tiers.normalize_sources("pmc")
    # Assert -- engine registered, alias resolves.
    assert (
        _tiers.ONLINE_ENGINES.get("PMC") is PMCSearchEngine,
        canonical,
    ) == (True, ["PMC"])
