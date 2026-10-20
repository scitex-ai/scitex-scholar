"""Slice 1 (old-direct unification): `?sources=` on the leaf search view.

Old-direct parity gap, measured 2026-10-19: hub's unified search takes
``?sources=a,b,c`` from the Sources checkbox grid; the leaf search view
took no ``sources`` parameter. These pins cover the thin HTTP adapter:
hub spellings map to canonical engine names, unknown names degrade to the
tiered default (never a 400), the selection rides the cache key, and the
echo lands in response metadata. Engines are injected fakes (PA-306).

House rule STX-TQ007: one assertion per pin -- multi-part outcomes ride
a single tuple comparison.
"""

import json
from pathlib import Path

import pytest
from django.test import RequestFactory

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
SEARCH_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
).read_text()


class _RecordingEngine:
    """Fake engine capturing the sources kwarg per call."""

    def __init__(self):
        self.calls = []

    async def search(self, query, mode=None, max_results=20, sources=None, filters=None, on_progress=None):
        self.calls.append(sources)
        return {"results": [], "metadata": {"engine_counts": {}}}


@pytest.fixture(autouse=True)
def _clear_search_cache():
    # Arrange -- the view's process-wide result cache outlives one test;
    # each pin starts uncached (house convention: views._cache.clear()).
    views._cache.clear()
    views._cache_timestamps.clear()


def test_search_passes_hub_source_spellings_as_canonical_names():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&sources=arxiv,pubmed")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (200, [["arXiv", "PubMed"]])


def test_search_drops_unknown_sources_without_failing():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&sources=arxiv,nope")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (200, [["arXiv"]])


def test_search_all_unknown_sources_keeps_tiered_default():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&sources=nope")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (200, [None])


def test_search_without_sources_keeps_tiered_default():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (200, [None])


def test_search_echoes_the_selection_in_response_metadata():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&sources=semantic")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert json.loads(resp.content)["metadata"]["sources_selected"] == [
        "Semantic_Scholar"
    ]


def test_search_cache_varies_by_source_selection():
    # Arrange -- the same query with two selections must fan out twice;
    # a shared cache entry would serve one selection's results to the other.
    engine = _RecordingEngine()
    rf = RequestFactory()
    # Act
    views.search(rf.get("/api/search?q=hippocampus&sources=arxiv"), _engine=engine)
    views.search(rf.get("/api/search?q=hippocampus&sources=pubmed"), _engine=engine)
    # Assert
    assert engine.calls == [["arXiv"], ["PubMed"]]


def test_search_rejects_overlong_sources_param():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&sources=" + "x" * 10_000)
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (400, [])


def test_advanced_block_carries_sources_grid():
    # Arrange
    # Act
    present = 'id="searchSourcesGrid"' in TEMPLATE
    # Assert
    assert present


def test_search_js_sends_checked_sources():
    # Arrange
    # Act
    present = "searchSourcesGrid" in SEARCH_JS
    # Assert
    assert present


def test_search_js_renders_per_source_counts():
    # Arrange
    # Act
    present = "engine_counts" in SEARCH_JS
    # Assert
    assert present


def test_sources_grid_offers_biorxiv_checkbox():
    # Arrange -- engine parity: the registered BioRxiv engine must be
    # selectable in the grid (hub old-direct source now in leaf).
    # Act
    present = 'value="biorxiv"' in TEMPLATE
    # Assert
    assert present
