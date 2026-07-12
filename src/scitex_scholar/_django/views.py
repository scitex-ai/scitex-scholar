#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Views for the scitex-scholar Django app.

Ports the Flask-era `scitex_scholar.gui._app` (`index`, `health`) and
`scitex_scholar.gui._routes_graph` (`graph_network`, `graph_related`,
`graph_paper`, `graph_health`) views verbatim in behaviour: same query
param validation, same in-memory TTL cache, same HTTP status codes
(400/404/500/503), same JSON response shapes. Only the framework
plumbing changes: `request.args` -> `request.GET`, `jsonify` -> Django
`JsonResponse`, `current_app.config` -> `django.conf.settings`.
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.parse
from typing import Dict, Optional

from django.conf import settings as django_settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

# Simple in-memory cache (framework-agnostic, ported verbatim)
_cache: Dict[str, dict] = {}
_cache_timestamps: Dict[str, float] = {}
_CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str) -> Optional[dict]:
    """Get value from cache if not expired."""
    if key in _cache:
        if time.time() - _cache_timestamps.get(key, 0) < _CACHE_TTL:
            return _cache[key]
        del _cache[key]
        del _cache_timestamps[key]
    return None


def _cache_set(key: str, value: dict, ttl: int = _CACHE_TTL):
    """Set value in cache."""
    _cache[key] = value
    _cache_timestamps[key] = time.time()


def _make_cache_key(prefix: str, doi: str, **kwargs) -> str:
    """Create cache key from parameters."""
    parts = [prefix, doi.lower()]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    return f"cg:{hashlib.md5(':'.join(parts).encode()).hexdigest()}"


def _db_path() -> Optional[str]:
    """Resolve the CrossRef DB path from Django settings."""
    return getattr(django_settings, "CROSSREF_DB_PATH", None)


def _get_builder():
    """Get or create CitationGraphBuilder for the configured DB."""
    db_path = _db_path()
    if not db_path:
        return None

    from scitex_scholar.citation_graph import CitationGraphBuilder

    return CitationGraphBuilder(db_path)


def _favicon_href() -> str:
    """Inline navy SVG favicon `data:` URI -- no static asset file needed."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#0a1e3f"/>'
        '<text x="16" y="22" font-size="16" font-family="sans-serif" '
        'fill="#ffffff" text-anchor="middle">S</text></svg>'
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg)


def index(request):
    """Serve the Scholar SPA shell page."""
    resolved_db = _db_path()
    html = render_to_string(
        "scholar/scholar.html",
        {
            "db_available": resolved_db is not None,
            "db_path": resolved_db or "Not found",
            "favicon_href": _favicon_href(),
        },
        request=request,
    )
    return HttpResponse(html)


@require_GET
def health(request):
    """Health check for the Scholar GUI service."""
    resolved_db = _db_path()
    return JsonResponse(
        {
            "status": "ok",
            "db_available": resolved_db is not None,
            "db_path": resolved_db,
        }
    )


@require_GET
def graph_network(request):
    """Build citation network for a DOI."""
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)

    try:
        top_n = int(request.GET.get("top_n", 20))
        top_n = max(1, min(50, top_n))
        weight_coupling = float(request.GET.get("weight_coupling", 2.0))
        weight_cocitation = float(request.GET.get("weight_cocitation", 2.0))
        weight_direct = float(request.GET.get("weight_direct", 1.0))
    except ValueError as e:
        return JsonResponse({"error": f"Invalid parameter: {e}"}, status=400)

    use_cache = request.GET.get("no_cache", "false").lower() != "true"

    # Check cache
    cache_key = _make_cache_key(
        "net",
        doi,
        top_n=top_n,
        wc=weight_coupling,
        wco=weight_cocitation,
        wd=weight_direct,
    )
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            cached["metadata"]["cached"] = True
            return JsonResponse(cached)

    # Build network
    builder = _get_builder()
    if not builder:
        return JsonResponse({"error": "CrossRef database not configured"}, status=503)

    try:
        graph = builder.build(
            seed_doi=doi,
            top_n=top_n,
            weight_coupling=weight_coupling,
            weight_cocitation=weight_cocitation,
            weight_direct=weight_direct,
        )
        result = graph.to_dict()
        result["metadata"]["cached"] = False

        # Mark seed node
        for node in result["nodes"]:
            node["is_seed"] = node["id"].lower() == doi.lower()

        _cache_set(cache_key, result)
        return JsonResponse(result)

    except FileNotFoundError:
        return JsonResponse({"error": "CrossRef database not found"}, status=503)
    except Exception as e:
        logger.error(f"Error building network for {doi}: {e}", exc_info=True)
        return JsonResponse({"error": f"Failed to build network: {e}"}, status=500)


@require_GET
def graph_related(request):
    """Get related papers for a DOI."""
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)

    try:
        limit = int(request.GET.get("limit", 10))
        limit = max(1, min(30, limit))
    except ValueError as e:
        return JsonResponse({"error": f"Invalid parameter: {e}"}, status=400)

    builder = _get_builder()
    if not builder:
        return JsonResponse({"error": "CrossRef database not configured"}, status=503)

    try:
        graph = builder.build(seed_doi=doi, top_n=limit)
        result = graph.to_dict()

        # Sort by similarity, exclude seed
        related = sorted(
            [n for n in result["nodes"] if n["id"].lower() != doi.lower()],
            key=lambda n: n.get("similarity_score", 0),
            reverse=True,
        )[:limit]

        return JsonResponse({"doi": doi, "related": related, "count": len(related)})

    except Exception as e:
        logger.error(f"Error getting related papers for {doi}: {e}", exc_info=True)
        return JsonResponse({"error": f"Failed to get related papers: {e}"}, status=500)


@require_GET
def graph_paper(request):
    """Get paper summary."""
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)

    builder = _get_builder()
    if not builder:
        return JsonResponse({"error": "CrossRef database not configured"}, status=503)

    try:
        summary = builder.get_paper_summary(doi)
        if summary:
            return JsonResponse(summary)
        return JsonResponse({"error": "Paper not found"}, status=404)

    except Exception as e:
        logger.error(f"Error getting paper summary for {doi}: {e}", exc_info=True)
        return JsonResponse({"error": f"Failed to get summary: {e}"}, status=500)


@require_GET
def graph_health(request):
    """Health check for citation graph service."""
    db_path = _db_path()
    if not db_path:
        return JsonResponse(
            {"status": "unhealthy", "error": "No database configured"}, status=503
        )

    try:
        builder = _get_builder()
        summary = builder.get_paper_summary("10.1038/s41586-020-2008-3")
        return JsonResponse(
            {
                "status": "healthy" if summary else "degraded",
                "database": db_path,
                "database_accessible": True,
            }
        )
    except Exception as e:
        return JsonResponse(
            {
                "status": "unhealthy",
                "database": db_path,
                "error": str(e),
            },
            status=503,
        )


# EOF
