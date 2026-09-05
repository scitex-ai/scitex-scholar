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

`search` has no Flask-era ancestor: it is a new adapter over the
package's `ScholarSearchEngine` facade, which is the single source of
truth for search. No search logic lives here.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Dict, Optional

from django.conf import settings as django_settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string

from django.apps import apps as _django_apps
from django.core.exceptions import ImproperlyConfigured

# The dotted INSTALLED_APPS entry a host must carry for these views to
# work. Kept as ONE string so the refusal below and the docs name the
# same thing (see apps.py for why the label is "scholar_editor").
APP_NAME = "scitex_scholar._django"
APP_CONFIG_PATH = "scitex_scholar._django.apps.ScholarEditorConfig"


def _refuse_unless_app_installed() -> None:
    """Fail at import when a host serves these views without our app.

    scitex-hub mounts this module's views under its own urlconf. On
    2026-09-05 prod did so WITHOUT adding `ScholarEditorConfig` to
    INSTALLED_APPS, so Django's app_directories loader never saw
    `scholar/scholar.html` and every logged-in request to /apps/scholar/v2/
    answered 500 `TemplateDoesNotExist` from `index`. Anonymous requests
    were redirected to login before reaching the view, so no curl probe
    ever showed it, and nobody knows how long it stood.

    Serving an app's views without installing the app is a declaration
    the host cannot honour, and it must fail where the cause is legible
    -- `manage.py check` and the host's urlconf import both import this
    module -- rather than evaporate into a 500 behind a login wall.

    Three-valued on purpose: the registry may not be READY when someone
    imports this module early (a script, a doc build). That is UNKNOWN,
    not "installed", and an import-time guard must not raise on unknown
    -- it stays silent and the request path answers as before. So this
    guard is a gate only where Django has finished loading apps, which
    is every place that can actually serve a request.
    """
    if not _django_apps.ready:
        return
    if _django_apps.is_installed(APP_NAME):
        return
    raise ImproperlyConfigured(
        f"{__name__} was imported, but '{APP_NAME}' is not in INSTALLED_APPS. "
        "Django's template loader only searches installed apps, so every page "
        "view here would answer 500 TemplateDoesNotExist (scholar/scholar.html). "
        f"Add '{APP_CONFIG_PATH}' (label 'scholar_editor') to the host "
        "project's INSTALLED_APPS next to the other mounted leaf apps."
    )


_refuse_unless_app_installed()

# scitex-app >= 0.8.0. Scholar previously COPIED this derivation from
# their 0.7.1 doc, with a comment claiming the copy kept the two from
# drifting. Events disproved that: the published derivation was WRONG
# for non-root views (request.path is the prefix PLUS the view's own
# route, and only the view knows its route), and scholar inherited the
# bug on copying it. A copy cannot drift from its source -- it also
# cannot receive its source's FIXES.
#
# view_path defaults to "", which is correct because index is
# registered at path("", ...). IF SCHOLAR EVER ADDS A NON-ROOT VIEW
# THAT EMITS THE MARKER, pass that view's route here; the function
# raises MountPrefixMismatch rather than guessing.
from scitex_app.embed import mount_prefix
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


def _api_url() -> Optional[str]:
    """Resolve the crossref-local HTTP endpoint from Django settings."""
    return getattr(django_settings, "CROSSREF_API_URL", None)


def _get_builder():
    """Get or create CitationGraphBuilder for the configured endpoint."""
    api_url = _api_url()
    if not api_url:
        return None

    from scitex_scholar.citation_graph import CitationGraphBuilder

    return CitationGraphBuilder(api_url=api_url)


_search_engine = None


def _get_search_engine():
    """Get the process-wide ScholarSearchEngine, constructing it on first use.

    The engine owns pooled pipelines and an API cache, so it is built once
    and reused rather than per request.
    """
    global _search_engine
    if _search_engine is None:
        from scitex_scholar import ScholarSearchEngine

        _search_engine = ScholarSearchEngine(
            email=getattr(django_settings, "SCHOLAR_EMAIL", None),
        )
    return _search_engine


def _app_label(base: str) -> str:
    """Tab title per the fleet ``SCITEX_APP_MODE`` convention.

    Mirrors scitex-storage's and scitex-writer's helper of the same name:
    the browser tab alone must distinguish a hub-embedded instance from a
    standalone one. Reads the Django setting that ``settings.py`` /
    ``_server.py`` configure, defaulting to "standalone"; hub's mount
    overrides it to "hub".

    This is also what supplies the page title at all. scitex-ui's shell
    renders ``<title>{{ app_label|default:"SciTeX App" }}</title>``, so an
    app that passes no ``app_label`` silently inherits the generic
    "SciTeX App" -- which is exactly what happened here when the local
    ``<title>`` was dropped in favour of the shell, and what
    ``test_index_body_contains_title`` caught.
    """
    from django.conf import settings

    mode = getattr(settings, "SCITEX_APP_MODE", "standalone")
    return f"{base} (hub)" if mode == "hub" else base


def index(request):
    """Serve the Scholar SPA shell page.

    No `favicon_href` is supplied: the template includes scitex-ui's
    branding partial, which ships the shared SciTeX mark. A locally
    hand-rolled icon here would SHADOW that mark (the partial honours
    favicon_href when given one) and drift from the rest of the fleet --
    which is what the removed `_favicon_href()` did.
    """
    resolved_api = _api_url()
    html = render_to_string(
        "scholar/scholar.html",
        {
            "api_available": resolved_api is not None,
            "api_url": resolved_api or "Not configured",
            "stx_mount": mount_prefix(request),
            "app_label": _app_label("SciTeX Scholar"),
        },
        request=request,
    )
    return HttpResponse(html)


@require_GET
def health(request):
    """Health check for the Scholar GUI service.

    Reports ``version`` so "is this deployment running what we shipped?" is
    answerable FROM OUTSIDE, over HTTP, without shell access to the host.

    That question was previously unanswerable by inspection, and the reason is
    worth recording: nothing scholar serves carried a version at all. Looking for
    one in the rendered page on 2026-08-23 produced a FALSE POSITIVE instead --
    the page matched "1.9.0", which turned out to be the substring inside a CDN
    url for ``highlight.js/11.9.0``. A substring search for a version number will
    find one on almost any page; it just will not be yours.

    KNOWN LIMITATION, stated because a version that lies is worse than none.
    ``__version__`` derives from ``importlib.metadata``, whose metadata is
    written at INSTALL time. For an EDITABLE checkout it therefore reports
    whatever ``pip install -e`` last recorded, not the code being served -- this
    repo's own .venv reports 1.5.1 while importing 1.9.0 source. So this field is
    trustworthy for a DEPLOYED (non-editable) install, which is the case it
    exists to serve, and must not be trusted in a dev checkout. Verify a dev tree
    by its import path, never by this number.
    """
    from scitex_scholar import __version__

    resolved_api = _api_url()
    return JsonResponse(
        {
            "status": "ok",
            "version": __version__,
            "api_available": resolved_api is not None,
            "api_url": resolved_api,
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
        return JsonResponse({"error": "CrossRef API not configured"}, status=503)

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
        return JsonResponse({"error": "CrossRef API not configured"}, status=503)

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
        return JsonResponse({"error": "CrossRef API not configured"}, status=503)

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
    api_url = _api_url()
    if not api_url:
        return JsonResponse(
            {"status": "unhealthy", "error": "No CrossRef API configured"}, status=503
        )

    try:
        builder = _get_builder()
        summary = builder.get_paper_summary("10.1038/s41586-020-2008-3")
        return JsonResponse(
            {
                "status": "healthy" if summary else "degraded",
                "api_url": api_url,
                "api_accessible": True,
            }
        )
    except Exception as e:
        return JsonResponse(
            {
                "status": "unhealthy",
                "api_url": api_url,
                "error": str(e),
            },
            status=503,
        )


@require_GET
def search(request):
    """Search academic databases through the package's ScholarSearchEngine.

    Thin HTTP adapter: query parsing, engine selection and result
    aggregation all belong to the package facade, so this view only
    validates parameters, delegates, and caches.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "q parameter required"}, status=400)

    try:
        max_results = int(request.GET.get("max_results", 20))
        max_results = max(1, min(100, max_results))
    except ValueError as e:
        return JsonResponse({"error": f"Invalid parameter: {e}"}, status=400)

    mode = request.GET.get("mode", "parallel")
    if mode not in ("parallel", "single"):
        return JsonResponse(
            {"error": "mode must be 'parallel' or 'single'"}, status=400
        )

    use_cache = request.GET.get("no_cache", "false").lower() != "true"
    cache_key = _make_cache_key("search", query, mode=mode, max_results=max_results)
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            cached["metadata"]["cached"] = True
            return JsonResponse(cached)

    try:
        engine = _get_search_engine()
        result = asyncio.run(
            engine.search(query=query, mode=mode, max_results=max_results)
        )
        result.setdefault("metadata", {})["cached"] = False
        _cache_set(cache_key, result)
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Search failed for {query!r}: {e}", exc_info=True)
        return JsonResponse({"error": f"Search failed: {e}"}, status=500)


# EOF
