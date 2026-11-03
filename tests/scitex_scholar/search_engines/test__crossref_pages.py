"""Page contract and real SQLite paging beyond the previous 1000-result ceiling."""
import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

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


def test_late_page_after_1000_has_no_overlap_with_first_page(corpus):
    # Arrange
    first = _page(corpus)
    # Act
    late = _page(corpus, offset=1000)
    # Assert
    assert (len(first["results"]), len(late["results"]),
            set(p["doi"] for p in first["results"]).isdisjoint(p["doi"] for p in late["results"]),
            late["metadata"]["pagination"]["total"], late["metadata"]["pagination"]["next_offset"], corpus[1]) == (
        50, 50, True, 1055, 1050, [("hippocampus", 50, 0), ("hippocampus", 50, 1000)],
    )


def test_final_partial_page_truthfully_reports_exhaustion(corpus):
    # Arrange
    offset = 1050
    # Act
    final = _page(corpus, offset=offset)
    # Assert
    assert (len(final["results"]), final["metadata"]["pagination"]["next_offset"],
            final["metadata"]["pagination"]["has_more"], corpus[1]) == (
        5, None, False, [("hippocampus", 50, offset)],
    )


def test_async_facade_delegates_a_late_page_without_global_pipeline_state(corpus):
    # Arrange
    engine = object.__new__(ScholarSearchEngine)
    engine.parallel_pipeline = _LocalPipeline()
    # Act
    result = asyncio.run(engine.search_page("hippocampus", offset=1000, page_size=50, _search=corpus[0]))
    # Assert
    assert (result["metadata"]["pagination"]["next_offset"], len(result["results"])) == (1050, 50)


def test_filters_advance_over_source_rows_instead_of_visible_rows(corpus):
    # Arrange
    filters = {"min_year": 2024}
    # Act
    result = _page(corpus, page_size=10, filters=filters, query="hippocampus year:2020-2024")
    page = result["metadata"]["pagination"]
    # Assert
    assert (len(result["results"]), {p["year"] for p in result["results"]}, page["source_returned"],
            page["total"], page["next_offset"], page["total_scope"]) == (
        2, {2024}, 10, 1055, 10, "source_matches_before_filters_and_deduplication",
    )


@pytest.mark.parametrize("offset,size", [(-1, 50), (0, 0), (0, 1001), (True, 50)])
def test_invalid_page_bounds_raise_before_provider_work(corpus, offset, size):
    # Arrange
    def request_page():
        return _page(corpus, offset=offset, page_size=size)
    # Act
    run = request_page
    # Assert
    with pytest.raises(ValueError):
        run()


@pytest.mark.parametrize("offset,size", [(-1, 50), (0, 0), (0, 1001), (True, 50)])
def test_invalid_page_bounds_leave_provider_unqueried(corpus, offset, size):
    # Arrange
    failure = None
    # Act
    try:
        _page(corpus, offset=offset, page_size=size)
    except ValueError as exc:
        failure = type(exc)
    # Assert
    assert (failure, corpus[1]) == (ValueError, [])


def test_empty_filtered_page_keeps_the_next_source_cursor(corpus):
    # Arrange
    filters = {"min_year": 2030}
    # Act
    result = _page(corpus, filters=filters)
    # Assert
    assert (result["results"], result["metadata"]["pagination"]["next_offset"]) == ([], 50)


def test_shell_filters_preserve_normalized_query_and_source_cursor(corpus):
    # Arrange
    query = 'hippocampus -t "paper 4" -ymin 2024'
    # Act
    result = _page(corpus, page_size=10, query=query)
    # Assert
    assert ([p["doi"] for p in result["results"]], corpus[1], result["metadata"]["pagination"]["next_offset"]) == (
        ["10.example/4"], [("hippocampus", 10, 0)], 10,
    )


def test_colon_year_and_excluded_keywords_preserve_source_total(corpus):
    # Arrange
    query = "hippocampus year:2024-2024 -9"
    # Act
    result = _page(corpus, page_size=10, query=query)
    # Assert
    assert ([p["doi"] for p in result["results"]], result["metadata"]["pagination"]["total"]) == (["10.example/4"], 1055)
