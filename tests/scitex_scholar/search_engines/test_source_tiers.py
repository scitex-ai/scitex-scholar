#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-tier execution: the NAD-local corpora must be what actually runs.

The review verdict on the first leaf-migration slice was: "``source_tiers`` is
declarative only; GUI pipelines still construct online PubMed/CrossRef/arXiv/
Semantic Scholar/OpenAlex, and metadata engines run concurrently. Implement
actual local Crossref/OpenAlex-primary ordering with online sources only as
explicit last fallback."

These tests pin the EXECUTION, not the declaration: which engines run for a
query, in which order, and what the response says about it. Everything is
offline -- the "local corpus" engines are stubs and the online ones record
whether they were called at all.
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


def _run(coro):
    return asyncio.run(coro)


# --- the policy itself -------------------------------------------------------


def test_declared_source_tiers_are_the_configured_policy():
    # Arrange / Act -- read through ScholarConfig, not a second hardcoded list.
    declared = tiers.declared_source_tiers()
    # Assert
    assert declared["primary"] == ["CrossRefLocal", "OpenAlexLocal"]
    assert declared["online_fallback"] == ["CrossRef", "OpenAlex"]


def test_local_tier_names_resolve_to_offline_corpus_adapters():
    # Arrange / Act
    primary, _ = tiers.build_tiered_engines()
    # Assert -- primary is local, and every entry is the corpus adapter (no
    # network client is constructed for a primary name).
    assert list(primary) == ["CrossRefLocal", "OpenAlexLocal"]
    assert all(isinstance(e, tiers.LocalCorpusSearchEngine) for e in primary.values())
    assert primary["CrossRefLocal"].sources == ("crossref",)
    assert primary["OpenAlexLocal"].sources == ("openalex",)


def test_fallback_tier_keeps_the_declared_order_and_all_declared_engines():
    # Arrange / Act
    _, fallback = tiers.build_tiered_engines()
    # Assert -- the declared fallbacks come FIRST (same corpora, public API)...
    assert list(fallback)[:2] == ["CrossRef", "OpenAlex"]
    # ...and the other configured databases are still reachable, because
    # dropping PubMed/arXiv/Semantic Scholar would change results silently.
    assert {"PubMed", "arXiv", "Semantic_Scholar"} <= set(fallback)


def test_unresolvable_primary_name_is_dropped_loudly():
    # Arrange -- a tier naming an adapter that does not exist.
    primary, _ = tiers.build_tiered_engines({"primary": ["Nope"], "online_fallback": []})
    # Assert -- dropped, not silently turned into an online engine.
    assert primary == {}


def test_resolve_tier_names_the_reason_for_the_fallback():
    # Arrange
    primary, _ = tiers.build_tiered_engines()
    # Act / Assert -- a corpus that answered.
    assert tiers.resolve_tier(3, primary) == ("primary", "")
    # ...a corpus that answered with nothing.
    assert tiers.resolve_tier(0, primary)[0] == "online_fallback"
    # ...and no primary tier at all.
    assert tiers.resolve_tier(0, {}) == (
        "online_fallback",
        "no primary (local corpus) engine configured",
    )


def test_resolve_tier_says_when_the_corpora_are_not_installed(monkeypatch):
    # Arrange -- the optional corpus packages are absent from this install.
    monkeypatch.setattr(tiers, "available_local_corpora", lambda: set())
    primary, _ = tiers.build_tiered_engines()
    # Act
    tier, reason = tiers.resolve_tier(0, primary)
    # Assert -- "not installed" is not reported as "returned no results".
    assert tier == "online_fallback" and "unavailable" in reason


def test_local_corpus_engine_returns_nothing_when_corpora_are_missing(monkeypatch):
    # Arrange
    monkeypatch.setattr(tiers, "available_local_corpora", lambda: set())
    engine = tiers.LocalCorpusSearchEngine("CrossRefLocal", ("crossref",))
    # Act -- must not raise, and must not touch the network.
    assert engine.search_by_keywords("hippocampus", max_results=5) == []


def test_local_corpus_work_maps_into_the_engines_result_shape(monkeypatch):
    # Arrange -- a fake corpus hit, in local_dbs' UnifiedWork shape. The
    # corpus packages are not installed here, so the package the engine
    # imports lazily is stubbed in sys.modules (the mapping is what is under
    # test, not the 167M-paper install).
    class _Work:
        doi = "10.1/local"
        title = "Local Corpus Paper"
        authors = ["L. Local"]
        year = 2023
        journal = "Local Journal"
        abstract = "from the NAS"
        citation_count = 12
        is_open_access = True
        oa_url = "https://example.org/a.pdf"

    class _Result:
        works = [_Work()]

    class _Unified:
        @staticmethod
        def search(*args, **kwargs):
            return _Result()

    import types

    package = types.ModuleType("scitex_scholar.local_dbs")
    package.unified = _Unified
    monkeypatch.setattr(tiers, "available_local_corpora", lambda: {"crossref"})
    monkeypatch.setitem(sys.modules, "scitex_scholar.local_dbs", package)
    engine = tiers.LocalCorpusSearchEngine("CrossRefLocal", ("crossref",))
    # Act
    (row,) = engine.search_by_keywords("anything", max_results=5)
    # Assert -- the same keys the online engines return, so the pipelines'
    # Paper conversion needs no special case.
    assert row["id"]["doi"] == "10.1/local"
    assert row["id"]["doi_engines"] == ["CrossRefLocal"]
    assert row["basic"]["title"] == "Local Corpus Paper"
    assert row["publication"] == {"year": 2023, "journal": "Local Journal"}
    assert row["metrics"]["citation_count"] == 12


def test_local_corpus_engine_survives_an_unimportable_corpus_package(monkeypatch):
    # Arrange -- the real failure mode of a deployment WITHOUT the optional
    # corpora: the local_dbs package itself raises ImportError (its __init__
    # re-exports shims that raise). The user's search must still run.
    import builtins

    real_import = builtins.__import__

    def _no_local_dbs(name, *args, **kwargs):
        if name.startswith("scitex_scholar.local_dbs"):
            raise ImportError("crossref-local not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(tiers, "available_local_corpora", lambda: {"crossref"})
    monkeypatch.setattr(builtins, "__import__", _no_local_dbs)
    engine = tiers.LocalCorpusSearchEngine("CrossRefLocal", ("crossref",))
    # Act
    results = engine.search_by_keywords("hippocampus", max_results=5)
    # Assert -- reported as "no results", which is what lets resolve_tier say
    # the corpora were unavailable instead of crashing the request.
    assert results == []


# --- execution: what actually runs for a query -------------------------------


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_local_corpus_answers_alone_and_online_is_never_queried(pipeline_cls):
    # Arrange -- both pipelines, because the policy must not apply to one mode
    # only: "single" is the rate-limited GUI option and would silently become
    # the online-first path.
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", raises=True)
    pipeline = pipeline_cls(
        engines={"CrossRefLocal": local, "CrossRef": online},
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )
    # Act
    out = _run(pipeline.search_async(query="hippocampus", max_results=10))
    # Assert
    assert local.calls and not online.calls
    assert out["metadata"]["source_tier"] == "primary"
    assert out["metadata"]["engines_used"] == ["CrossRefLocal"]
    assert [r["title"] for r in out["results"]] == ["Hit"]


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_online_is_reached_only_after_the_local_corpus_returns_nothing(pipeline_cls):
    # Arrange -- the local corpus is present but has no match.
    local = _StubEngine("CrossRefLocal", results=[])
    online = _StubEngine("CrossRef", results=[_result("10.2/y", "Online Hit")])
    pipeline = pipeline_cls(
        engines={"CrossRefLocal": local, "CrossRef": online},
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )
    # Act
    out = _run(pipeline.search_async(query="obscure query", max_results=10))
    # Assert -- the fallback ran BECAUSE the local tier was empty, and the
    # response says so (a silent fallback is the defect being fixed).
    assert local.calls and online.calls
    assert out["metadata"]["source_tier"] == "online_fallback"
    assert out["metadata"]["source_tier_reason"] == "local corpora returned no results"
    assert [r["title"] for r in out["results"]] == ["Online Hit"]


def test_primary_hit_stops_at_the_local_tier_even_with_fewer_than_max_results():
    # Arrange -- one local hit for a 50-result request: coverage alone must not
    # trigger the network, or the fallback would be the normal path again.
    local = _StubEngine("CrossRefLocal", results=[_result("10.3/z", "Only Hit")])
    online = _StubEngine("CrossRef", raises=True)
    pipeline = ScholarPipelineSearchParallel(
        engines={"CrossRefLocal": local, "CrossRef": online},
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )
    # Act
    out = _run(pipeline.search_async(query="hippocampus", max_results=50))
    # Assert
    assert not online.calls and out["metadata"]["source_tier"] == "primary"


def test_search_metadata_reports_both_tiers_for_readiness():
    # Arrange
    local = _StubEngine("CrossRefLocal", results=[_result("10.4/a", "Hit")])
    pipeline = ScholarPipelineSearchParallel(
        engines={"CrossRefLocal": local, "CrossRef": _StubEngine("CrossRef")},
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )
    # Act
    meta = _run(pipeline.search_async(query="q", max_results=5))["metadata"]
    # Assert -- a deployment can answer "did this go to the network?" from the
    # response alone.
    assert meta["primary_engines"] == ["CrossRefLocal"]
    assert meta["fallback_engines"] == ["CrossRef"]
    assert meta["total_engines"] == 1
