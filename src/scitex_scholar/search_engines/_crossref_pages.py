"""Page-sized access to the local Crossref corpus without a total-result cap.

The provider's total counts source matches BEFORE Scholar's post-search
threshold filters and page-local DOI/title deduplication. It is never advertised
as a count of filtered or globally deduplicated papers.
"""
from __future__ import annotations

import re
from datetime import datetime

from scitex_scholar.core import Paper
from scitex_scholar.pipelines.SearchQueryParser import SearchQueryParser


class UnsupportedPageFilter(ValueError):
    """A query requests metadata this provider cannot filter reliably."""


def search_crossref_page(query, *, offset, page_size, filters, pipeline, search=None):
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    if search is None:
        from crossref_local import search

    started = datetime.now()
    if re.search(r"(?:^|\s)(?:-[taj]|-ymin|-ymax|-cmin|-cmax|-ifmin|-ifmax|--title|--author|--journal|--year-min|--year-max|--citations-min|--citations-max|--if-min|--if-max)\s", query):
        shell = SearchQueryParser.from_shell_syntax(query).get_filters()
        parsed = SearchQueryParser(" ".join(shell.get("positive_keywords", []))).get_filters()
        parsed.update({key: value for key, value in shell.items() if key != "positive_keywords"})
    else:
        parsed = SearchQueryParser(query).get_filters()
    combined = {**parsed, **(filters or {})}
    unsupported = {"open_access", "document_type"}.intersection(combined)
    if unsupported:
        raise UnsupportedPageFilter(
            "Paged local Crossref cannot reliably filter open-access status or document type. "
            "Use a bounded search with an appropriate additional source for these filters."
        )
    for old, new in (("year_start", "min_year"), ("year_end", "max_year")):
        if old in combined:
            combined.setdefault(new, combined[old])
    if not parsed.get("positive_keywords"):
        raise UnsupportedPageFilter("Paged local Crossref search requires a keyword as well as any filters.")
    clean_query = " ".join(parsed["positive_keywords"])
    raw = search(clean_query, limit=page_size, offset=offset)
    works = list(raw.works)
    total = raw.total
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise RuntimeError("Crossref returned an invalid source match count")
    if not works and offset < total:
        raise RuntimeError("Crossref returned an empty page before its reported total")
    papers = []
    for work in works:
        paper = Paper()
        paper.metadata.id.doi = work.doi
        paper.metadata.id.doi_engines = ["CrossRefLocal"]
        paper.metadata.basic.title = work.title
        paper.metadata.basic.authors = list(work.authors or [])
        paper.metadata.basic.abstract = work.abstract
        paper.metadata.basic.year = work.year
        paper.metadata.publication.journal = work.journal
        paper.metadata.publication.impact_factor = getattr(work, "impact_factor", None)
        paper.metadata.citation_count.total = work.citation_count
        fields = {
            "title": work.title or "",
            "author": " ".join(str(author) for author in (work.authors or [])),
            "journal": work.journal or "",
        }
        haystack = (fields["title"] + " " + (work.abstract or "")).casefold()
        if any(str(term).casefold() in haystack for term in combined.get("negative_keywords", [])):
            continue
        if any(
            any(str(term).casefold() not in text.casefold() for term in combined.get(field + "_includes", []))
            or any(str(term).casefold() in text.casefold() for term in combined.get(field + "_excludes", []))
            for field, text in fields.items()
        ):
            continue
        papers.append(paper)
    papers = pipeline._deduplicate_papers(papers)
    papers = pipeline._enrich_impact_factors(papers)
    papers = pipeline._apply_threshold_filters(papers, combined)
    results = [pipeline._paper_to_dict(paper) for paper in papers]
    for result in results:
        result["source"] = "CrossRefLocal"
    next_offset = offset + len(works)
    has_more = bool(works) and next_offset < total
    return {
        "results": results,
        "metadata": {
            "query": clean_query,
            "original_query": query,
            "parsed_query": clean_query,
            "filters": combined,
            "total_results": len(results),
            "engines_used": ["CrossRefLocal"],
            "engine_counts": {"CrossRefLocal": len(results)},
            "engine_events": [{"engine": "CrossRefLocal", "status": "completed", "count": len(results)}],
            "sources_selected": ["CrossRefLocal"],
            "source_tier": "selected",
            "search_time": (datetime.now() - started).total_seconds(),
            "cached": False,
            "pagination": {
                "source": "CrossRefLocal",
                "offset": offset,
                "page_size": page_size,
                "source_returned": len(works),
                "returned": len(results),
                "total": total,
                "total_scope": "source_matches_before_filters_and_deduplication",
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
            },
        },
    }
