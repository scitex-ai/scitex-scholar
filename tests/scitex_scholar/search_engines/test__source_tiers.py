#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-tier execution: the NAS-local corpora must be what actually runs.

The review verdict on the first leaf-migration slice was: "``source_tiers`` is
declarative only; GUI pipelines still construct online PubMed/CrossRef/arXiv/
Semantic Scholar/OpenAlex, and metadata engines run concurrently. Implement
actual local Crossref/OpenAlex-primary ordering with online sources only as
explicit last fallback."

These tests pin the EXECUTION, not the declaration: which engines run for a
query, in which order, and what the response says about it. Everything is
offline -- the engines are hand-rolled fakes passed in through the pipelines'
``engines=`` parameter, and the online fakes record whether they were called at
all. No mocks, no patching: the collaborators are parameters (PA-306).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(_REPO_ROOT / "src") not in sys.path:  # same guard tests elsewhere use
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from scitex_scholar.pipelines.ScholarPipelineSearchParallel import (  # noqa: E402
    ScholarPipelineSearchParallel,
)
from scitex_scholar.pipelines.ScholarPipelineSearchSingle import (  # noqa: E402
    ScholarPipelineSearchSingle,
)
from scitex_scholar.search_engines import _source_tiers as tiers  # noqa: E402


def _result(doi: str, title: str) -> dict:
    """One engine result in the standardized shape the pipelines consume."""
    return {
        "id": {"doi": doi, "doi_engines": ["stub"]},
        "basic": {"title": title, "authors": ["A. Author"], "abstract": "abs"},
        "publication": {"year": 2024, "journal": "J. Test"},
        "metrics": {"citation_count": 3, "is_open_access": False},
    }


class _StubEngine:
    """A search engine that reports what it was asked and how often."""

    def __init__(self, name: str, results: list = None, raises: bool = False):
        self.name = name
        self.results = results or []
        self.raises = raises
        self.calls: list = []

    def search_by_keywords(self, query, filters=None, max_results=100):
        self.calls.append(query)
        if self.raises:
            raise AssertionError(f"{self.name} was queried; it must not be")
        return list(self.results)


class _Work:
    """The ``local_dbs.unified`` UnifiedWork shape, as the adapter sees it."""

    def __init__(self):
        self.doi = "10.1/local"
        self.title = "Local Corpus Paper"
        self.authors = ["L. Local"]
        self.year = 2023
        self.journal = "Local Journal"
        self.abstract = "from the NAS"
        self.citation_count = 12
        self.is_open_access = True
        self.oa_url = "https://example.org/a.pdf"


class _CorpusResult:
    """A UnifiedSearchResult stand-in holding one work."""

    def __init__(self):
        self.works = [_Work()]


def _corpus_search(query, limit, sources):
    """A hand-rolled corpus reader: no network, no database."""
    return _CorpusResult()


def _pipeline(pipeline_cls, engines: dict):
    return pipeline_cls(
        engines=engines,
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )


def _run(coro):
    return asyncio.run(coro)


# --- the policy the config declares ------------------------------------------


def test_declared_source_tiers_name_the_local_corpora_primary():
    # Arrange
    expected = ["CrossRefLocal", "OpenAlexLocal"]
    # Act
    declared = tiers.declared_source_tiers()
    # Assert
    assert declared["primary"] == expected


def test_declared_source_tiers_name_the_online_apis_as_fallback():
    # Arrange
    expected = ["CrossRef", "OpenAlex"]
    # Act
    declared = tiers.declared_source_tiers()
    # Assert
    assert declared["online_fallback"] == expected


def test_local_tier_names_resolve_to_corpus_adapters():
    # Arrange
    expected = ["CrossRefLocal", "OpenAlexLocal"]
    # Act
    primary, _ = tiers.build_tiered_engines()
    # Assert
    assert list(primary) == expected


def test_primary_tier_engines_are_offline_corpus_adapters():
    # Arrange
    def is_adapter(engine):
        return isinstance(engine, tiers.LocalCorpusSearchEngine)

    # Act
    primary, _ = tiers.build_tiered_engines()
    # Assert
    assert all(is_adapter(engine) for engine in primary.values())


def test_each_primary_engine_queries_the_corpus_its_name_names():
    # Arrange
    expected = (("crossref",), ("openalex",))
    # Act
    primary, _ = tiers.build_tiered_engines()
    # Assert
    assert tuple(engine.sources for engine in primary.values()) == expected


def test_fallback_tier_starts_with_the_declared_online_apis():
    # Arrange
    expected = ["CrossRef", "OpenAlex"]
    # Act
    _, fallback = tiers.build_tiered_engines()
    # Assert
    assert list(fallback)[:2] == expected


def test_fallback_tier_keeps_every_configured_online_engine():
    # Arrange -- dropping PubMed/arXiv/Semantic Scholar would change results
    # silently, so the ORDER is the policy, not the coverage.
    keep = {"PubMed", "arXiv", "Semantic_Scholar"}
    # Act
    _, fallback = tiers.build_tiered_engines()
    # Assert
    assert keep <= set(fallback)


def test_unresolvable_primary_name_is_dropped_not_retried_online():
    # Arrange
    declared = {"primary": ["Nope"], "online_fallback": []}
    # Act
    primary, fallback = tiers.build_tiered_engines(declared)
    # Assert
    assert (list(primary), "Nope" in fallback) == ([], False)


# --- tier resolution, with the reason ----------------------------------------


def test_resolve_tier_reports_a_local_answer():
    # Arrange
    primary, _ = tiers.build_tiered_engines()
    # Act
    resolution = tiers.resolve_tier(3, primary)
    # Assert
    assert resolution == ("primary", "")


def test_resolve_tier_reports_an_empty_local_answer():
    # Arrange -- the corpora ARE installed here, they just matched nothing.
    installed = lambda: {"crossref", "openalex"}  # noqa: E731
    primary, _ = tiers.build_tiered_engines(available=installed)
    # Act
    tier, reason = tiers.resolve_tier(0, primary, available=installed)
    # Assert
    assert (tier, reason) == ("online_fallback", "local corpora returned no results")


def test_resolve_tier_reports_a_missing_primary_tier():
    # Arrange
    no_primary: dict = {}
    # Act
    resolution = tiers.resolve_tier(0, no_primary)
    # Assert
    assert resolution == (
        "online_fallback",
        "no primary (local corpus) engine configured",
    )


def test_resolve_tier_reports_absent_corpora_as_unavailable():
    # Arrange -- the optional corpus packages are absent from this install.
    primary, _ = tiers.build_tiered_engines(available=lambda: set())
    # Act
    _, reason = tiers.resolve_tier(0, primary, available=lambda: set())
    # Assert
    assert reason.startswith("local corpora unavailable")


def test_resolve_tier_falls_back_when_the_corpora_are_absent():
    # Arrange
    primary, _ = tiers.build_tiered_engines(available=lambda: set())
    # Act
    tier, _ = tiers.resolve_tier(0, primary, available=lambda: set())
    # Assert
    assert tier == "online_fallback"


# --- the corpus adapter ------------------------------------------------------


def test_corpus_work_maps_into_the_engines_result_shape():
    # Arrange -- the same keys the online engines return, so the pipelines'
    # Paper conversion needs no special case.
    engine = tiers.LocalCorpusSearchEngine(
        "CrossRefLocal",
        ("crossref",),
        available=lambda: {"crossref"},
        search=_corpus_search,
    )
    expected = {
        "id": {"doi": "10.1/local", "doi_engines": ["CrossRefLocal"]},
        "basic": {
            "title": "Local Corpus Paper",
            "authors": ["L. Local"],
            "abstract": "from the NAS",
        },
        "publication": {"year": 2023, "journal": "Local Journal"},
        "metrics": {"citation_count": 12, "is_open_access": True},
        "urls": {
            "doi_url": "https://doi.org/10.1/local",
            "pdf": "https://example.org/a.pdf",
        },
    }
    # Act
    results = engine.search_by_keywords("anything", max_results=5)
    # Assert
    assert results == [expected]


def test_corpus_engine_returns_nothing_when_the_corpus_is_absent():
    # Arrange -- an install without crossref-local.
    engine = tiers.LocalCorpusSearchEngine(
        "CrossRefLocal", ("crossref",), available=lambda: set()
    )
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=5)
    # Assert
    assert results == []


def test_corpus_engine_returns_nothing_when_the_corpus_package_is_missing():
    # Arrange -- the real failure mode: local_dbs raises ImportError when its
    # optional packages are absent (reported as CorpusUnavailable).
    def _raise(query, limit, sources):
        raise tiers.CorpusUnavailable("crossref-local not installed")

    engine = tiers.LocalCorpusSearchEngine(
        "CrossRefLocal", ("crossref",), available=lambda: {"crossref"}, search=_raise
    )
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=5)
    # Assert
    assert results == []


@pytest.mark.skipif(
    tiers.available_local_corpora() != set(),
    reason="this install has the local corpora; the missing-package path cannot run",
)
def test_default_corpus_lookup_reports_the_missing_package():
    # Arrange -- this environment genuinely lacks crossref_local/openalex_local.
    # Act
    raised = pytest.raises(tiers.CorpusUnavailable)
    # Assert
    with raised:
        tiers.default_corpus_search("hippocampus", limit=5, sources=["crossref"])


# --- execution: what actually runs for a query -------------------------------


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_local_corpus_answers_alone_and_online_is_never_queried(pipeline_cls):
    # Arrange -- both modes: "single" is the rate-limited GUI option and was
    # online-first too.
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", raises=True)
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", max_results=10))
    # Assert
    assert (bool(local.calls), bool(online.calls)) == (True, False)


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_local_answer_is_reported_as_the_primary_tier(pipeline_cls):
    # Arrange
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", raises=True)
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", max_results=10))
    # Assert
    assert out["metadata"]["source_tier"] == "primary"


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_online_is_reached_only_after_the_local_corpus_returns_nothing(pipeline_cls):
    # Arrange -- the local corpus is present but has no match.
    local = _StubEngine("CrossRefLocal", results=[])
    online = _StubEngine("CrossRef", results=[_result("10.2/y", "Online Hit")])
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="obscure query", max_results=10))
    # Assert
    assert (bool(local.calls), bool(online.calls)) == (True, True)


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_fallback_answer_is_reported_with_its_reason(pipeline_cls):
    # Arrange -- a silent fallback is the defect being fixed.
    local = _StubEngine("CrossRefLocal", results=[])
    online = _StubEngine("CrossRef", results=[_result("10.2/y", "Online Hit")])
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="obscure query", max_results=10))
    # Assert
    assert (
        out["metadata"]["source_tier"],
        out["metadata"]["source_tier_reason"],
    ) == ("online_fallback", "local corpora returned no results")


def test_fallback_results_are_the_ones_rendered():
    # Arrange
    local = _StubEngine("CrossRefLocal", results=[])
    online = _StubEngine("CrossRef", results=[_result("10.2/y", "Online Hit")])
    pipeline = _pipeline(
        ScholarPipelineSearchParallel,
        {"CrossRefLocal": local, "CrossRef": online},
    )
    # Act
    out = _run(pipeline.search_async(query="obscure query", max_results=10))
    # Assert
    assert [paper["title"] for paper in out["results"]] == ["Online Hit"]


def test_primary_hit_stops_at_the_local_tier_below_max_results():
    # Arrange -- one local hit for a 50-result request: low coverage alone must
    # not trigger the network, or the fallback becomes the normal path again.
    local = _StubEngine("CrossRefLocal", results=[_result("10.3/z", "Only Hit")])
    online = _StubEngine("CrossRef", raises=True)
    pipeline = _pipeline(
        ScholarPipelineSearchParallel,
        {"CrossRefLocal": local, "CrossRef": online},
    )
    # Act
    out = _run(pipeline.search_async(query="hippocampus", max_results=50))
    # Assert
    assert (bool(online.calls), out["metadata"]["source_tier"]) == (False, "primary")


def test_search_metadata_reports_the_tier_membership_for_readiness():
    # Arrange -- a deployment can answer "did this go to the network?" from the
    # response alone.
    local = _StubEngine("CrossRefLocal", results=[_result("10.4/a", "Hit")])
    pipeline = _pipeline(
        ScholarPipelineSearchParallel,
        {"CrossRefLocal": local, "CrossRef": _StubEngine("CrossRef")},
    )
    # Act
    meta = _run(pipeline.search_async(query="q", max_results=5))["metadata"]
    # Assert
    assert (meta["primary_engines"], meta["fallback_engines"]) == (
        ["CrossRefLocal"],
        ["CrossRef"],
    )
