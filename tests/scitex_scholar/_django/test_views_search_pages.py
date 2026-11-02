"""HTTP page bounds and delegation; real SQLite semantics have their own mirror."""
import json

import pytest
from django.test import RequestFactory
from scitex_scholar._django import views

class _PageEngine:
    def __init__(self):
        self.calls = []

    async def search_page(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return {"results": [], "metadata": {"pagination": {"total": 1055, "next_offset": 1050}}}


def test_api_keeps_offset_beyond_1000_and_passes_validated_filters():
    # Arrange
    engine = _PageEngine()
    # Act
    response = views.search_page(RequestFactory().get("/api/search/page", {"q": "hippocampus", "sources": "crossref_local", "offset": "1000", "page_size": "50", "year_from": "2024"}), _engine=engine)
    # Assert
    assert (response.status_code, engine.calls, json.loads(response.content)["metadata"]["pagination"]["total"]) == (
        200, [("hippocampus", {"offset": 1000, "page_size": 50, "filters": {"min_year": 2024}})], 1055,
    )


@pytest.mark.parametrize("params", [
    {"sources": "crossref_local,openalex"}, {"sources": "crossref"},
    {"sources": "crossref_local", "offset": "-1"},
    {"sources": "crossref_local", "page_size": "1001"},
])
def test_page_api_rejects_unsupported_source_and_bad_bounds(params):
    # Arrange
    engine = _PageEngine()
    # Act
    response = views.search_page(RequestFactory().get("/api/search/page", {"q": "hippocampus", **params}), _engine=engine)
    # Assert
    assert (response.status_code, engine.calls) == (400, [])
