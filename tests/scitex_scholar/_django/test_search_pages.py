"""Page contract and real SQLite paging beyond the previous 1000-result ceiling."""
import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from scitex_scholar._django import views
from scitex_scholar.pipelines.ScholarPipelineSearchParallel import ScholarPipelineSearchParallel
from scitex_scholar.search_engines._crossref_pages import search_crossref_page
from scitex_scholar.search_engines.ScholarSearchEngine import ScholarSearchEngine


class _LocalPipeline(ScholarPipelineSearchParallel):
    """Keep the genuine normalization/filter logic without external enrichment."""
    def __init__(self):
        self.name = "LocalPageTest"

    def _enrich_impact_factors(self, papers):
        return papers


@pytest.fixture
def corpus():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE VIRTUAL TABLE papers USING fts5(title, doi UNINDEXED, year UNINDEXED)")
    db.executemany("INSERT INTO papers VALUES (?, ?, ?)", [
        (f"hippocampus paper {i}", f"10.example/{i}", 2020 + i % 5)
        for i in range(1055)
    ])
    calls = []

    def search(query, *, limit, offset):
        calls.append((query, limit, offset))
        total = db.execute("SELECT COUNT(*) FROM papers WHERE papers MATCH ?", (query,)).fetchone()[0]
        rows = db.execute("SELECT title, doi, year FROM papers WHERE papers MATCH ? ORDER BY rowid LIMIT ? OFFSET ?", (query, limit, offset))
        works = [SimpleNamespace(title=title, doi=doi, year=int(year), authors=[], abstract="", journal="Example", citation_count=0) for title, doi, year in rows]
        return SimpleNamespace(works=works, total=total)

    yield search, calls
    db.close()


def _page(corpus, offset=0, page_size=50, filters=None, query="hippocampus"):
    search, _ = corpus
    return search_crossref_page(query, offset=offset, page_size=page_size, filters=filters, pipeline=_LocalPipeline(), search=search)


def test_real_sqlite_page_after_1000_retains_total_and_reaches_exhaustion(corpus):
    first = _page(corpus)
    late = _page(corpus, offset=1000)
    final = _page(corpus, offset=1050)
    assert len(first["results"]) == len(late["results"]) == 50
    assert set(p["doi"] for p in first["results"]).isdisjoint(p["doi"] for p in late["results"])
    assert late["metadata"]["pagination"]["total"] == 1055
    assert late["metadata"]["pagination"]["next_offset"] == 1050
    assert len(final["results"]) == 5
    assert final["metadata"]["pagination"]["next_offset"] is None
    assert not final["metadata"]["pagination"]["has_more"]
    assert corpus[1] == [("hippocampus", 50, 0), ("hippocampus", 50, 1000), ("hippocampus", 50, 1050)]


def test_async_facade_delegates_a_late_page_without_global_pipeline_state(corpus):
    engine = object.__new__(ScholarSearchEngine)
    engine.parallel_pipeline = _LocalPipeline()
    result = asyncio.run(engine.search_page("hippocampus", offset=1000, page_size=50, _search=corpus[0]))
    assert result["metadata"]["pagination"]["next_offset"] == 1050
    assert len(result["results"]) == 50


def test_filters_keep_source_total_and_advance_over_scanned_not_visible_rows(corpus):
    result = _page(corpus, page_size=10, filters={"min_year": 2024}, query="hippocampus year:2020-2024")
    page = result["metadata"]["pagination"]
    assert len(result["results"]) == 2
    assert all(p["year"] == 2024 for p in result["results"])
    assert page["source_returned"] == 10
    assert page["total"] == 1055
    assert page["next_offset"] == 10
    assert page["total_scope"] == "source_matches_before_filters_and_deduplication"


@pytest.mark.parametrize("offset,size", [(-1, 50), (0, 0), (0, 1001), (True, 50)])
def test_invalid_page_bounds_never_query_provider(corpus, offset, size):
    with pytest.raises(ValueError):
        _page(corpus, offset=offset, page_size=size)
    assert corpus[1] == []


def test_empty_filtered_page_still_has_next_source_page(corpus):
    result = _page(corpus, filters={"min_year": 2030})
    assert result["results"] == []
    assert result["metadata"]["pagination"]["next_offset"] == 50


def test_shell_syntax_and_year_filters_apply_without_changing_source_cursor(corpus):
    result = _page(corpus, page_size=10, query='hippocampus -t "paper 4" -ymin 2024')
    assert [paper["doi"] for paper in result["results"]] == ["10.example/4"]
    assert corpus[1] == [("hippocampus", 10, 0)]
    assert result["metadata"]["pagination"]["next_offset"] == 10


def test_colon_year_and_excluded_keyword_filters_are_retained(corpus):
    result = _page(corpus, page_size=10, query="hippocampus year:2024-2024 -9")
    assert [paper["doi"] for paper in result["results"]] == ["10.example/4"]
    assert result["metadata"]["pagination"]["total"] == 1055


class _PageEngine:
    def __init__(self):
        self.calls = []

    async def search_page(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return {"results": [], "metadata": {"pagination": {"total": 1055, "next_offset": 1050}}}


def test_api_keeps_offset_beyond_1000_and_passes_validated_filters():
    engine = _PageEngine()
    response = views.search_page(RequestFactory().get("/api/search/page", {"q": "hippocampus", "sources": "crossref_local", "offset": "1000", "page_size": "50", "year_from": "2024"}), _engine=engine)
    assert response.status_code == 200
    assert engine.calls == [("hippocampus", {"offset": 1000, "page_size": 50, "filters": {"min_year": 2024}})]
    assert json.loads(response.content)["metadata"]["pagination"]["total"] == 1055


@pytest.mark.parametrize("params", [
    {"sources": "crossref_local,openalex"}, {"sources": "crossref"},
    {"sources": "crossref_local", "offset": "-1"},
    {"sources": "crossref_local", "page_size": "1001"},
])
def test_page_api_rejects_unsupported_source_and_bad_bounds(params):
    engine = _PageEngine()
    response = views.search_page(RequestFactory().get("/api/search/page", {"q": "hippocampus", **params}), _engine=engine)
    assert response.status_code == 400
    assert engine.calls == []
