#!/usr/bin/env python3
"""Shared post-search threshold filters (old-direct unification slice 2).

Both search pipelines trim merged results by year / citation / impact-factor
bounds here, so parallel and single mode honor the same range filters --
old-direct's Filters section applies server-side whatever the mode. A paper
missing the year fails BOTH year bounds (an undated paper must not pass a
year gate either way); missing citations/impact factor read as 0, so they
fail lower bounds and pass upper bounds >= 0. Callers normalize hub
spellings (year_from/...) to these ``min_year``/``max_year``/
``min_citations``/``max_citations``/``min_impact_factor``/
``max_impact_factor`` keys before calling.
"""

from __future__ import annotations

from typing import Any, Dict, List

import scitex_logging as logging

from scitex_scholar.core import Paper

logger = logging.getLogger(__name__)


def apply_threshold_filters(papers: List[Paper], filters: Dict[str, Any]) -> List[Paper]:
    """Trim papers to the min/max year, citation, and impact-factor bounds.

    Args:
        papers: Merged, deduplicated papers.
        filters: Threshold bounds; absent keys mean unbounded on that side.

    Returns:
        Filtered list of papers.
    """
    filtered_papers = []
    filter_stats = {
        "min_year": 0,
        "max_year": 0,
        "min_citations": 0,
        "max_citations": 0,
        "min_impact_factor": 0,
        "max_impact_factor": 0,
    }

    for paper in papers:
        # Check year range
        if "min_year" in filters:
            try:
                min_year = int(filters["min_year"])
                year = (
                    paper.metadata.basic.year
                    if hasattr(paper.metadata, "basic")
                    else None
                )
                if not year or year < min_year:
                    filter_stats["min_year"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        if "max_year" in filters:
            try:
                max_year = int(filters["max_year"])
                year = (
                    paper.metadata.basic.year
                    if hasattr(paper.metadata, "basic")
                    else None
                )
                if not year or year > max_year:
                    filter_stats["max_year"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        # Check minimum citations
        if "min_citations" in filters:
            try:
                min_citations = int(filters["min_citations"])
                citations = 0
                if hasattr(paper.metadata, "citation_count"):
                    citations = paper.metadata.citation_count.total or 0
                if citations < min_citations:
                    filter_stats["min_citations"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        # Check maximum citations
        if "max_citations" in filters:
            try:
                max_citations = int(filters["max_citations"])
                citations = None
                if hasattr(paper.metadata, "citation_count"):
                    citations = paper.metadata.citation_count.total
                if citations is not None and citations > max_citations:
                    filter_stats["max_citations"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        # Check minimum impact factor
        if "min_impact_factor" in filters:
            try:
                min_if = float(filters["min_impact_factor"])
                impact_factor = 0.0
                if (
                    hasattr(paper.metadata, "publication")
                    and paper.metadata.publication.impact_factor
                ):
                    impact_factor = paper.metadata.publication.impact_factor or 0.0
                if impact_factor < min_if:
                    filter_stats["min_impact_factor"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        # Check maximum impact factor (a missing factor reads as 0.0, same
        # convention as the minimum bound, so it passes any max >= 0).
        if "max_impact_factor" in filters:
            try:
                max_if = float(filters["max_impact_factor"])
                impact_factor = 0.0
                if (
                    hasattr(paper.metadata, "publication")
                    and paper.metadata.publication.impact_factor
                ):
                    impact_factor = paper.metadata.publication.impact_factor or 0.0
                if impact_factor > max_if:
                    filter_stats["max_impact_factor"] += 1
                    continue
            except (ValueError, AttributeError):
                pass

        # Paper passed all filters
        filtered_papers.append(paper)

    # Log filter statistics
    total_filtered = sum(filter_stats.values())
    if total_filtered > 0:
        filter_msgs = [
            f"{count} by {name}"
            for name, count in filter_stats.items()
            if count > 0
        ]
        logger.info(
            f"Threshold filters: filtered {total_filtered} papers ({', '.join(filter_msgs)}), "
            f"{len(filtered_papers)} remain"
        )

    return filtered_papers


# EOF
