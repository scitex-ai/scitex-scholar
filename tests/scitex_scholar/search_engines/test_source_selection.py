#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 1 (old-direct unification): explicit per-source search selection.

Old-direct parity gap, measured 2026-10-19: hub's unified search takes
``?sources=a,b,c`` from the Sources checkbox grid (crossref_local,
openalex_local, pubmed, arxiv, semantic, crossref, openalex) and runs the
checked sources; the leaf search view takes no ``sources`` parameter and the
tiered pipelines always decide themselves. This slice threads an explicit
selection from the view through the engine into both pipelines: a selection
runs exactly those engines in parallel (no tier short-circuit), while the
absent/empty case keeps the current tiered behaviour untouched.
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

    def __init__(self, name: str, results: list = None):
        self.name = name
        self.results = results or []
        self.calls: list = []

    def search_by_keywords(self, query, filters=None, max_results=100):
        self.calls.append(query)
        return list(self.results)


def _pipeline(pipeline_cls, engines: dict):
    return pipeline_cls(
        engines=engines,
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )


def _run(coro):
    return asyncio.run(coro)


# --- name normalization: hub/UI spelling -> canonical engine names -----------


def test_normalize_sources_maps_hub_names_to_canonical_engines():
    # Arrange
    raw = "crossref_local,openalex_local,pubmed,arxiv,semantic,crossref,openalex"
    # Act
    out = tiers.normalize_sources(raw)
    # Assert
    assert out == [
        "CrossRefLocal",
        "OpenAlexLocal",
        "PubMed",
        "arXiv",
        "Semantic_Scholar",
        "CrossRef",
        "OpenAlex",
    ]


def test_normalize_sources_drops_unknown_names():
    # Arrange
    # Act
    out = tiers.normalize_sources("arxiv,nope,pubmed")
    # Assert
    assert out == ["arXiv", "PubMed"]


def test_normalize_sources_empty_means_tiered_default():
    # Arrange
    # Act
    out = tiers.normalize_sources("")
    # Assert
    assert out is None


def test_normalize_sources_all_unknown_means_tiered_default():
    # Arrange -- degrade to the default path, never fail the search.
    # Act
    out = tiers.normalize_sources("nope,nada")
    # Assert
    assert out is None


# --- execution: an explicit selection runs exactly those engines -------------


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_explicit_selection_runs_only_the_selected_engines(pipeline_cls):
    # Arrange
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", results=[_result("10.1/y", "Other")])
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    _run(pipeline.search_async(query="hippocampus", sources=["CrossRef"]))
    # Assert
    assert (bool(local.calls), bool(online.calls)) == (False, True)


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_explicit_selection_skips_the_tier_short_circuit(pipeline_cls):
    # Arrange -- the local corpus HAS an answer, yet the user asked for the
    # online source alone: the explicit selection wins over the tier policy.
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", results=[_result("10.1/y", "Other")])
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", sources=["CrossRef"]))
    # Assert
    assert out["metadata"]["source_tier"] == "selected"


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_explicit_selection_reports_per_engine_counts(pipeline_cls):
    # Arrange
    online = _StubEngine("CrossRef", results=[_result("10.1/y", "Other")])
    pipeline = _pipeline(pipeline_cls, {"CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", sources=["CrossRef"]))
    # Assert
    assert out["metadata"]["engine_counts"] == {"CrossRef": 1}


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_absent_selection_keeps_tiered_behaviour(pipeline_cls):
    # Arrange
    local = _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])
    online = _StubEngine("CrossRef", results=[_result("10.1/y", "Other")])
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": local, "CrossRef": online})
    # Act
    out = _run(pipeline.search_async(query="hippocampus"))
    # Assert
    assert out["metadata"]["source_tier"] == "primary"
