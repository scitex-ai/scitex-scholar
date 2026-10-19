#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 2 (old-direct unification): explicit range filters on search.

Old-direct parity gap, measured 2026-10-19: hub's Filters section (year /
citations / impact-factor sliders) feeds hidden inputs (year_from/year_to,
min|max citations/impact-factor) into the unified search, which filters
server-side. The leaf honors range filters only through query syntax --
and only where the pipeline applies them: the parallel pipeline never saw
max_citations/max_impact_factor, and the single pipeline applies no
thresholds at all. These pins cover both pipelines end-to-end with stub
engines: min/max on year, citations, and impact factor trim results in
parallel AND single mode alike.
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


def _result(doi: str, title: str, year: int = 2024, citations: int = 3) -> dict:
    """One engine result in the standardized shape the pipelines consume."""
    return {
        "id": {"doi": doi, "doi_engines": ["stub"]},
        "basic": {"title": title, "authors": ["A. Author"], "abstract": "abs"},
        "publication": {"year": year, "journal": "J. Test"},
        "metrics": {"citation_count": citations, "is_open_access": False},
    }


class _StubEngine:
    """A search engine returning a fixed result set."""

    def __init__(self, name: str, results: list = None):
        self.name = name
        self.results = results or []

    def search_by_keywords(self, query, filters=None, max_results=100):
        return list(self.results)


def _pipeline(pipeline_cls, engines: dict):
    return pipeline_cls(
        engines=engines,
        source_tiers={"primary": ["CrossRefLocal"], "online_fallback": ["CrossRef"]},
    )


def _run(coro):
    return asyncio.run(coro)


def _one_hit_engine():
    return _StubEngine("CrossRefLocal", results=[_result("10.1/x", "Hit")])


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_min_year_trims_results_in_both_modes(pipeline_cls):
    # Arrange -- the stub paper is from 2024.
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", filters={"min_year": 2025}))
    # Assert
    assert out["results"] == []


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_max_year_trims_results_in_both_modes(pipeline_cls):
    # Arrange
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(pipeline.search_async(query="hippocampus", filters={"max_year": 2023}))
    # Assert
    assert out["results"] == []


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_min_citations_trims_results_in_both_modes(pipeline_cls):
    # Arrange -- the stub paper has 3 citations.
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(
        pipeline.search_async(query="hippocampus", filters={"min_citations": 10})
    )
    # Assert
    assert out["results"] == []


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_max_citations_trims_results_in_both_modes(pipeline_cls):
    # Arrange -- the stub paper has 3 citations.
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(
        pipeline.search_async(query="hippocampus", filters={"max_citations": 2})
    )
    # Assert
    assert out["results"] == []


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_matching_ranges_keep_results_in_both_modes(pipeline_cls):
    # Arrange
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(
        pipeline.search_async(
            query="hippocampus",
            filters={
                "min_year": 2020,
                "max_year": 2024,
                "min_citations": 1,
                "max_citations": 10,
                "max_impact_factor": 0,
            },
        )
    )
    # Assert -- the stub paper (2024, 3 cites, no IF reads as 0.0) survives.
    assert len(out["results"]) == 1


@pytest.mark.parametrize(
    "pipeline_cls",
    [ScholarPipelineSearchParallel, ScholarPipelineSearchSingle],
    ids=["parallel", "single"],
)
def test_min_impact_factor_trims_factorless_results_in_both_modes(pipeline_cls):
    # Arrange -- the stub paper carries no impact factor (reads as 0.0).
    pipeline = _pipeline(pipeline_cls, {"CrossRefLocal": _one_hit_engine()})
    # Act
    out = _run(
        pipeline.search_async(query="hippocampus", filters={"min_impact_factor": 1.0})
    )
    # Assert
    assert out["results"] == []
