"""Slice 2 (old-direct unification): range-filter params on the search view.

Old-direct parity gap, measured 2026-10-19: hub's Filters sliders feed
year_from/year_to + min|max citations/impact-factor into the unified
search; the leaf view takes none of them (ranges work only through query
syntax, and max bounds not even there). These pins cover the thin HTTP
adapter: hub param names map to the pipeline threshold keys, malformed
numbers and inverted ranges fail closed (400), and the filters ride the
cache key. Engines are injected fakes (PA-306).
"""

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
    """Fake engine capturing the filters kwarg per call."""

    def __init__(self):
        self.calls = []

    async def search(self, query, mode=None, max_results=20, sources=None, filters=None):
        self.calls.append(filters)
        return {"results": [], "metadata": {"engine_counts": {}}}


@pytest.fixture(autouse=True)
def _clear_search_cache():
    # Arrange -- the view's process-wide result cache outlives one test;
    # each pin starts uncached (house convention: views._cache.clear()).
    views._cache.clear()
    views._cache_timestamps.clear()


def test_search_maps_hub_range_params_to_threshold_keys():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get(
        "/api/search?q=hippocampus&year_from=2020&year_to=2024"
        "&min_citations=5&max_citations=100"
        "&min_impact_factor=1.5&max_impact_factor=20"
    )
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (
        200,
        [
            {
                "min_year": 2020,
                "max_year": 2024,
                "min_citations": 5,
                "max_citations": 100,
                "min_impact_factor": 1.5,
                "max_impact_factor": 20.0,
            }
        ],
    )


def test_search_without_range_params_passes_no_filters():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (200, [None])


def test_search_rejects_non_integer_year():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&year_from=recently")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (400, [])


def test_search_rejects_inverted_year_range():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get(
        "/api/search?q=hippocampus&year_from=2024&year_to=2020"
    )
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (400, [])


def test_search_rejects_out_of_range_year():
    # Arrange
    engine = _RecordingEngine()
    request = RequestFactory().get("/api/search?q=hippocampus&year_from=999")
    # Act
    resp = views.search(request, _engine=engine)
    # Assert
    assert (resp.status_code, engine.calls) == (400, [])


def test_search_cache_varies_by_range_filters():
    # Arrange -- the same query with two ranges must fan out twice.
    engine = _RecordingEngine()
    rf = RequestFactory()
    # Act
    views.search(rf.get("/api/search?q=hippocampus&year_from=2020"), _engine=engine)
    views.search(rf.get("/api/search?q=hippocampus&year_from=2021"), _engine=engine)
    # Assert
    assert [c["min_year"] for c in engine.calls] == [2020, 2021]


def test_advanced_block_carries_year_range_inputs():
    # Arrange
    # Act
    present = ('id="searchYearFrom"' in TEMPLATE, 'id="searchYearTo"' in TEMPLATE)
    # Assert
    assert present == (True, True)


def test_advanced_block_carries_citation_range_inputs():
    # Arrange
    # Act
    present = (
        'id="searchMinCitations"' in TEMPLATE,
        'id="searchMaxCitations"' in TEMPLATE,
    )
    # Assert
    assert present == (True, True)


def test_advanced_block_carries_impact_range_inputs():
    # Arrange
    # Act
    present = (
        'id="searchMinImpact"' in TEMPLATE,
        'id="searchMaxImpact"' in TEMPLATE,
    )
    # Assert
    assert present == (True, True)


def test_search_js_sends_range_params():
    # Arrange
    # Act
    present = ("year_from" in SEARCH_JS, "min_citations" in SEARCH_JS)
    # Assert
    assert present == (True, True)
