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
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import scitex_logging as slogging

# The whole `[server]` stack is OPTIONAL for the DISTRIBUTION (a bare
# `pip install scitex-scholar` must not pull Django) and REQUIRED for THIS
# module -- a Django view set has no meaning without the framework. Each
# import is therefore GUARDED (2026-09-20) and each guard FAILS LOUDLY with
# the extra to install; none of them silently degrades to a missing name.
# See apps.py for why a silent guard is unacceptable on this surface.
try:
    from django.apps import apps as _django_apps
    from django.conf import settings as django_settings
    from django.core.exceptions import ImproperlyConfigured
    from django.http import HttpResponse, JsonResponse
    from django.template.loader import render_to_string
    from django.utils.translation import gettext as _i18n  # noqa: N816  (JS string dict)
    from django.views.decorators.http import require_GET, require_POST
except ImportError as exc:  # django absent -- the [server] capability only
    raise ImportError(
        "scitex_scholar._django.views needs Django, which is not installed. "
        "Install the server extra: pip install 'scitex-scholar[server]'"
    ) from exc

try:
    from scitex_app.embed import mount_prefix
except ImportError as exc:  # scitex-app absent -- the [server] capability only
    raise ImportError(
        "scitex_scholar._django.views needs scitex-app, which is not "
        "installed. Install the server extra: pip install 'scitex-scholar[server]'"
    ) from exc

try:
    from scitex_ui.project_scope import (
        LocalProjectProvider,
        host_project_provider,
        project_listing_view,
        resolve_project,
    )
except ImportError as exc:  # scitex-ui absent -- the [server] capability only
    raise ImportError(
        "scitex_scholar._django.views needs scitex-ui, which is not "
        "installed. Install the server extra: pip install 'scitex-scholar[server]'"
    ) from exc

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

logger = slogging.getLogger(__name__)

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


# The Django setting that names crossref-local's HTTP endpoint. Namespaced,
# because a host (scitex-hub) defines it in ITS settings module, where a bare
# `CROSSREF_API_URL` is one collision away from meaning something else.
# Hub already exports the same spelling as an env var, so host and leaf now
# agree on one name (hub request, 2026-09-05).
CROSSREF_API_URL_SETTING = "SCITEX_SCHOLAR_CROSSREF_API_URL"

# Pre-1.11 spelling. Honoured for ONE release so hosts can migrate, and LOUD
# when used: a silent alias would leave the host believing the old name is
# still a supported one right up to the release that deletes it.
CROSSREF_API_URL_SETTING_DEPRECATED = "CROSSREF_API_URL"
_CROSSREF_ALIAS_REMOVAL = "1.12.0"
_warned_deprecated_setting = False


def _api_url() -> Optional[str]:
    """Resolve the crossref-local HTTP endpoint from Django settings.

    Reads ``SCITEX_SCHOLAR_CROSSREF_API_URL`` first; it always wins when
    both spellings are set. The bare ``CROSSREF_API_URL`` is read second,
    once per process with a warning naming both spellings. ``None`` under
    either name means "not configured", never "fall through".
    """
    global _warned_deprecated_setting

    value = getattr(django_settings, CROSSREF_API_URL_SETTING, None)
    if value is not None:
        return value
    legacy = getattr(django_settings, CROSSREF_API_URL_SETTING_DEPRECATED, None)
    if legacy is not None:
        if not _warned_deprecated_setting:
            _warned_deprecated_setting = True
            logger.warning(
                "Django setting %s is deprecated and will be removed in "
                "scitex-scholar %s; define %s instead. Using the value from "
                "%s for now.",
                CROSSREF_API_URL_SETTING_DEPRECATED,
                _CROSSREF_ALIAS_REMOVAL,
                CROSSREF_API_URL_SETTING,
                CROSSREF_API_URL_SETTING_DEPRECATED,
            )
        return legacy
    return None


# The three citation-graph BUILD routes (network/related/paper) answer 503 when
# no crossref-local endpoint is configured: they are user-initiated actions, and
# a failed action is truthfully a 5xx. The HEALTH route is different and must
# never be 5xx -- it is called on the normal initial-load path, and a capability
# report is not a failed request (see graph_health).
#
# The body was the wrong ANSWER — "CrossRef API not configured" states what
# broke and not what to do, which leaves a first-time user stuck with no next
# step (measured 2026-09-02 as a standalone first-run blocker). Built once and
# shared so the routes cannot drift into different explanations.
def _not_configured_payload() -> dict:
    """The 'no crossref-local endpoint' body, with the fix in it."""
    return {
        "error": "CrossRef API not configured",
        "detail": (
            "The citation graph reads its data from a crossref-local HTTP API; "
            "scholar never opens the corpus files itself. No endpoint is "
            "configured, so there is nothing to query."
        ),
        "fix": (
            f"Set {CROSSREF_API_URL_SETTING} to a running crossref-local "
            "endpoint (env var of the same name, or the Django setting when "
            "scholar is mounted in a host project), then restart the server. "
            "Installing the `crossref-local` package supplies a default "
            "endpoint, which scholar falls back to when the variable is unset."
        ),
        "setting": CROSSREF_API_URL_SETTING,
        "docs": "src/scitex_scholar/citation_graph/README.md",
    }


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
    try:
        from django.conf import settings
    except ImportError as exc:  # django absent -- the [server] capability only
        raise ImportError(
            "scitex_scholar._django.views needs Django, which is not "
            "installed. Install the server extra: "
            "pip install 'scitex-scholar[server]'"
        ) from exc

    mode = getattr(settings, "SCITEX_APP_MODE", "standalone")
    return f"{base} (hub)" if mode == "hub" else base


def _standalone_projects_root() -> Path:
    """Return the folder the standalone scitex-ui provider lists."""
    explicit = os.environ.get("SCITEX_SCHOLAR_PROJECTS_DIR")
    if explicit:
        return Path(explicit).expanduser()
    library_root = os.environ.get("SCITEX_SCHOLAR_LIBRARY_ROOT")
    if library_root:
        return Path(library_root).expanduser()
    scitex_root = Path(os.environ.get("SCITEX_DIR", "~/.scitex")).expanduser()
    return scitex_root / "scholar" / "library"


class ScholarLocalProjectProvider(LocalProjectProvider):
    """scitex-ui's standalone provider, minus the library's reserved dirs.

    scitex-ui's ::class:`LocalProjectProvider` treats EVERY non-hidden folder
    under its root as a selectable project. Scholar's standalone root IS the
    library root, whose direct children also include ``MASTER/`` (the
    deduplicated paper store) and ``downloads/`` (the PDF staging area), so the
    stock provider offered the internal store as if it were a user project.

    Subclassing (rather than reimplementing) keeps scitex-ui authoritative for
    the picker's id/name/detail shape and for the stored last-visited file,
    while the LISTING follows Scholar's own storage contract. The reserved
    names come from ``storage._project_reconcile`` -- the same set the library
    reconciler and audit use -- so the picker and the storage layer cannot
    disagree about what a project is.
    """

    def list_projects(self, request=None):
        """Projects the picker may offer: real project dirs only."""
        from scitex_scholar.storage._project_reconcile import RESERVED_LIBRARY_DIRS

        reserved = {name.upper() for name in RESERVED_LIBRARY_DIRS}
        return [
            entry
            for entry in super().list_projects(request)
            # Case-insensitive: a "master" folder is the same internal store on
            # a case-insensitive filesystem, and MUST NOT slip through here.
            if entry.name.upper() not in reserved
            and not (self.root / entry.name).is_symlink()
        ]


def _project_provider(request):
    """Use the mounted host provider, or scitex-ui's local provider standalone."""
    return host_project_provider() or ScholarLocalProjectProvider(
        _standalone_projects_root()
    )


# Shared scitex-ui GET-list / POST-remember endpoint. The provider factory is
# request-time so mounted hosts remain authoritative for permissions and
# project identity; Scholar contains no Hub model or authorization logic.
project_scope = project_listing_view(_project_provider)


def index(request):
    """Serve the Scholar SPA shell page.

    No `favicon_href` is supplied: the template includes scitex-ui's
    branding partial, which ships the shared SciTeX mark. A locally
    hand-rolled icon here would SHADOW that mark (the partial honours
    favicon_href when given one) and drift from the rest of the fleet --
    which is what the removed `_favicon_href()` did.
    """
    resolved_api = _api_url()
    provider = _project_provider(request)
    current_project = resolve_project(
        request,
        provider,
        explicit=request.GET.get("project"),
    )
    html = render_to_string(
        "scholar/scholar.html",
        {
            "api_available": resolved_api is not None,
            "api_url": resolved_api or "Not configured",
            "stx_mount": mount_prefix(request),
            "app_label": _app_label("SciTeX Scholar"),
            "app_scope": "project",
            "current_project": current_project,
            # i18n (operator directive 2026-09-14): the whole page flips via
            # LocaleMiddleware; this carries the strings that live ONLY in
            # JS, translated server-side for the current request language so
            # the client never hardcodes a language. Serialized by the
            # template's json_script filter into <script id="SCHOLAR_I18N">;
            # the client reads it via JSON.parse (see scholarT in stx-mount.js).
            "scholar_i18n": _js_i18n_dict(),
            # The scitex-ui workspace shell renders three side panes
            # (Console/Chat, Files, Viewer) around the app content. Scholar
            # has no content for them, and because the template extends the
            # shell directly (it is not a built SPA shell the SDK wraps) they
            # would otherwise render empty — the large left gutter on desktop
            # and the broken reflow on mobile. Declare them unused so the
            # shell hides them and Scholar is the whole page. This is the
            # shell's documented contract ("panes ... DECLARED by the app").
            "panes": {"ai": "unused", "files": "unused", "viewer": "unused"},
        },
        request=request,
    )
    return HttpResponse(html)


def _js_i18n_dict() -> dict:
    """The JS-only strings, translated for the CURRENT request language.

    Built once per render so the active language (django_language cookie on
    the hub; browser locale standalone) is honoured. Keys are the English
    source strings; the client looks them up in window["SCHOLAR_I18N"]. A
    key with `%(name)s` is interpolated client-side (scholarT).
    """
    return {
        "Build citation graph": _i18n("Build citation graph"),
        "Build Graph": _i18n("Build Graph"),
        "Enrich": _i18n("Enrich"),
        "Graph Controls": _i18n("Graph Controls"),
        "Ignore cache": _i18n("Ignore cache"),
        "Unknown authors": _i18n("Unknown authors"),
        "Untitled": _i18n("Untitled"),
        "Service available": _i18n("Service available"),
        "Service limited": _i18n("Service limited"),
        "Service unavailable": _i18n("Service unavailable"),
        # Citation Graph capability: endpoint configured but not yet probed --
        # deliberately not "available", since the backend has not answered.
        "Not checked yet": _i18n("Not checked yet"),
        "Unknown": _i18n("Unknown"),
        "Checking...": _i18n("Checking..."),
        "Related papers": _i18n("Related papers"),
        "Papers": _i18n("Papers"),
        "Paper": _i18n("Paper"),
        "char abstract": _i18n("char abstract"),
        "citations": _i18n("citations"),
        "Enriched: %(parts)s": _i18n("Enriched: %(parts)s"),
        "Enriching…": _i18n("Enriching…"),
        "Enrichment failed": _i18n("Enrichment failed"),
        "Enrichment failed (HTTP %(status)s)": _i18n("Enrichment failed (HTTP %(status)s)"),
        # Library states (review blocker 2): every message below is rendered by
        # library.js, so it MUST be a key here -- an English literal in the JS
        # is invisible to the catalog and shows EN on a JA page.
        "Your library is empty. Import a BibTeX file to add papers.": _i18n(
            "Your library is empty. Import a BibTeX file to add papers."
        ),
        "No papers match the current filters.": _i18n(
            "No papers match the current filters."
        ),
        "Clear filters": _i18n("Clear filters"),
        "Import BibTeX": _i18n("Import BibTeX"),
        "%(count)s of %(total)s Papers": _i18n("%(count)s of %(total)s Papers"),
        # Search tab: the empty result state was an English literal in search.js.
        "No papers matched this query.": _i18n("No papers matched this query."),
        # Search tab: which tier answered (local NAS corpora vs online fallback).
        "Local corpus (NAS)": _i18n("Local corpus (NAS)"),
        "Online fallback": _i18n("Online fallback"),
        "Imported %(n)s paper from %(file)s": _i18n("Imported %(n)s paper from %(file)s"),
        "Imported %(n)s papers from %(file)s": _i18n("Imported %(n)s papers from %(file)s"),
    }


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
        return JsonResponse(_not_configured_payload(), status=503)

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
        return JsonResponse(_not_configured_payload(), status=503)

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
        return JsonResponse(_not_configured_payload(), status=503)

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
    """Capability report for the citation graph. NEVER answers 5xx.

    WHY NOT 5xx (measured 2026-09-17): the initial Scholar load called this
    route unconditionally, so an unconfigured optional backend turned every
    page load into a same-origin 503 -- and a host that refuses to allowlist
    5xx cannot front that. The status code was also the wrong SHAPE: this is a
    capability REPORT, not a failed request, and the report itself always
    succeeds; the body is where the truth belongs.

    Two modes, so the expensive part happens only when the feature is opened:

    * default      -> configuration only, NO network call (the initial load);
    * ``?probe=1`` -> the live canary probe, run when the Citation Graph tab is
      activated.

    Truthful states, never masked: ``unconfigured`` (nothing to query, with the
    fix), ``configured`` (endpoint present, not probed yet), ``healthy``,
    ``degraded`` (reachable but the canary returned nothing) and ``unavailable``
    (configured and the probe FAILED -- reported as unavailable, never as
    ready).
    """
    api_url = _api_url()
    if not api_url:
        return JsonResponse(
            {"status": "unconfigured", "probed": False, **_not_configured_payload()}
        )

    if request.GET.get("probe") != "1":
        return JsonResponse(
            {
                "status": "configured",
                "probed": False,
                "error": "Citation Graph: not checked",
                "detail": (
                    "A crossref-local endpoint is configured. The graph backend "
                    "is probed when you open the Citation Graph tab, so a slow "
                    "or unreachable backend cannot delay the rest of the page."
                ),
                "fix": "Open the Citation Graph tab to check it.",
            }
        )

    try:
        builder = _get_builder()
        summary = builder.get_paper_summary("10.1038/s41586-020-2008-3")
        if summary:
            return JsonResponse({"status": "healthy", "probed": True})
        # Configured and reachable but the canary probe returned no data — the
        # capability is limited, not broken (previously fell through to a bare
        # "Service limited / Unknown" because the client never handled it).
        return JsonResponse({**_degraded_payload(), "probed": True})
    except Exception:
        # Configured but unreachable/errored — LIMITED WITH THE CAUSE AND THE
        # FIX, and still not a 5xx: the request succeeded, the capability did
        # not. The raw exception string is deliberately not returned (it can
        # name internal hosts).
        return JsonResponse(
            {
                "status": "unavailable",
                "probed": True,
                "error": "Citation Graph: unavailable",
                "detail": (
                    "The crossref-local endpoint is configured but could not "
                    "be reached right now, so citation graphs cannot be built."
                ),
                "fix": (
                    "Verify the crossref-local service is running and that "
                    "the endpoint is reachable, then retry."
                ),
            }
        )


def _degraded_payload() -> dict:
    """The limited-state body for a reachable-but-empty canary probe.

    Built as a pure helper so the degraded branch is testable without mocking
    the network: the view returns ``_degraded_payload()`` verbatim when the
    builder answers with no data for the canary DOI.
    """
    return {
        "status": "degraded",
        "error": "Citation Graph: limited",
        "detail": (
            "The crossref-local endpoint is configured and reachable, but the "
            "probe returned no data for the canary paper. Citation graphs may "
            "be incomplete."
        ),
        "fix": (
            "Check that the crossref-local endpoint is serving the corpus you "
            "expect; the citation graph depends on it."
        ),
    }


@require_GET
def search(request, _engine=None):
    """Search academic databases through the package's ScholarSearchEngine.

    Thin HTTP adapter: query parsing, engine selection and result
    aggregation all belong to the package facade, so this view only
    validates parameters, delegates, and caches.

    `_engine` is a test-injection seam: the collaborator is a PARAMETER, not a
    monkeypatch (PA-306), exactly as `library_enrich(_pipeline=)` is. Django
    routes call it with only `request`.
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
        engine = _engine or _get_search_engine()
        result = asyncio.run(
            engine.search(query=query, mode=mode, max_results=max_results)
        )
        result.setdefault("metadata", {})["cached"] = False
        _cache_set(cache_key, result)
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Search failed for {query!r}: {e}", exc_info=True)
        return JsonResponse({"error": f"Search failed: {e}"}, status=500)


# ---------------------------------------------------------------------------
# Library API (#106: metadata enrichment as a contextual Library operation).
#
# Thin HTTP adapters over the package's own storage and enrichment layer --
# the same code the `scitex-scholar library` CLI drives. No library or
# enrichment logic lives in these views:
#   list  -> storage._library_index (user's local library index)
#   enrich-> storage.PaperIO (master metadata.json) +
#            pipelines.ScholarPipelineMetadataSingle (the enrichment engine)
#
# USER SCOPE: standalone scholar has no account system; the user's library is
# the local, per-user directory (~/.scitex/scholar/library) -- the same store
# the CLI reads, satisfying the operator's "standalone works without an
# account; the local library is the default" constraint (2026-09-02). The
# SCITEX_SCHOLAR_LIBRARY_ROOT env var is a test seam set in the SERVER
# process, not an HTTP parameter, so an unauthenticated client cannot redirect
# the API to another user's library.
# ---------------------------------------------------------------------------


def _library_root() -> Path:
    """The library root for the STANDALONE local user (or the server-side env
    override used in tests). Default: the user's home library."""
    override = os.environ.get("SCITEX_SCHOLAR_LIBRARY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    from scitex_scholar._cli._library_shared import default_library_root

    return default_library_root()


def _safe_username(user) -> str:
    """A request user reduced to a single safe path component."""
    name = str(getattr(user, "username", None) or getattr(user, "pk", "") or "user")
    # Only keep alnum / underscore / hyphen; collapse the rest so the result
    # can never escape its parent directory (no separators, no dot, no NUL).
    name = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in name)
    return name or "user"


def _mounted_user_root(user) -> Path:
    """Per-request-user library root for a MOUNTED (hub) deployment.

    The hub runs one server process (a service account), so the process-global
    home library must NOT be shared across authenticated users. Scope each user
    to their own directory. The base is set by the host via
    SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE (the explicit integration seam the hub
    configures); a safe default keeps it contained if unset.
    """
    base = os.environ.get("SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE")
    if not base:
        base = str(Path.home() / ".scitex" / "scholar" / "mounted")
    return Path(base) / _safe_username(user)


def _library_root_for(request) -> Path:
    """Resolve the library root a request operates on, per user.

    Precedence:
      1. Explicit integration seam: a mounted host (or a test) binds the
         request's root by setting ``request.scholar_library_root``. This is the
         seam the hub uses to give each authenticated user their own library.
      2. Authenticated hub user (and no explicit binding): a per-user scoped
         root, so the shared service-account home is never exposed to everyone.
      3. Standalone local user: the home library (or the server-side
         SCITEX_SCHOLAR_LIBRARY_ROOT env override used in tests).
    """
    bound = getattr(request, "scholar_library_root", None)
    if bound:
        return Path(bound).expanduser().resolve()
    user = getattr(request, "user", None)
    # is_anonymous is a BOOL property on a real Django user (AbstractBaseUser),
    # not a method -- calling it (the old `getattr(user, 'is_anonymous',
    # lambda: True)()`) raised TypeError for every authenticated hub user and
    # 500'd all three library endpoints on the live /v2/ route. Read it as a
    # value, tolerating a callable only for non-Django mocks.
    is_anon = getattr(user, "is_anonymous", True)
    if callable(is_anon):
        is_anon = is_anon()
    if user is not None and getattr(user, "is_authenticated", False) and not is_anon:
        return _mounted_user_root(user)
    return _library_root()


def _assert_safe_library_id(library_id: str) -> str:
    """A persisted library_id is a single path component under MASTER/.

    It must not contain a path separator, NUL, or be a traversal token --
    otherwise ``MASTER/<library_id>`` could escape the library root.
    """
    if not library_id or "/" in library_id or "\\" in library_id or "\x00" in library_id:
        raise ValueError(f"unsafe library_id: {library_id!r}")
    if library_id in (".", ".."):
        raise ValueError("unsafe library_id: traversal token")
    return library_id


def _load_library_paper(root: Path, paper_id: str):
    """Load one master metadata.json as a Paper, keyed by paper_id.

    Real library files store {"metadata": {...}} with no "container", so the
    paper_id is set explicitly -- that is what PaperIO needs to write back to
    the same MASTER/<paper_id>/ directory on save.
    """
    from scitex_scholar.core.Paper import Paper

    meta_path = root / "MASTER" / paper_id / "metadata.json"
    data = json.loads(meta_path.read_text())
    paper = Paper.from_dict(data)
    paper.container.library_id = paper_id
    return paper


def _save_library_paper(paper, root: Path) -> Path:
    """Persist an enriched Paper to its master dir.

    The library is the user's local MASTER files; the view writes them directly
    (PaperIO) and does NOT touch the shared relational library index -- that
    store is keyed by the running user, and rebuilding it here would couple the
    GUI to a store the app may not own. Reading back is done straight from the
    master files (see library_list), which is the same user-scope guarantee.

    The library_id is validated to be a single safe path component BEFORE any
    write, so MASTER/<library_id> can never escape the library root.
    """
    from scitex_scholar.storage.PaperIO import PaperIO

    library_id = _assert_safe_library_id(paper.container.library_id)
    io = PaperIO(paper, base_dir=root / "MASTER")
    return io.save_metadata()


@require_GET
def library_list(request):
    """List the user's local library papers, optionally filtered by ``?q=``.

    Returns {papers: [...], count, total, filtered, query, library_root}.
    Reads the user's MASTER metadata files directly (``collect_rows`` -- "no
    store involved"), scoped to the request's user (see ``_library_root_for``),
    so a mounted hub never exposes one shared service-account library to every
    user. An empty or missing library is an empty list, not an error.

    ``filtered`` says whether a filter was APPLIED, and ``total`` how many
    papers the library holds before it. The client needs both to tell "you have
    no papers" from "your filter matched none" -- the two states carry
    different copy and different actions, and without the flag the filtered
    empty state is dead code no user can ever reach.
    """
    root = _library_root_for(request)
    from scitex_scholar.storage import _library_index as idx

    query = (request.GET.get("q") or "").strip()

    def _payload(papers: list, total: int) -> dict:
        return {
            "papers": papers,
            "count": len(papers),
            "total": total,
            "filtered": bool(query),
            "query": query,
            "library_root": str(root),
        }

    try:
        rows = idx.collect_rows(root)
    except FileNotFoundError:
        return JsonResponse(_payload([], 0))
    except ValueError as e:
        # Duplicate DOIs across MASTER entries == library corruption; surface it
        # rather than silently listing an inconsistent view.
        logger.error(f"library list: {e}")
        return JsonResponse({"error": f"Library index inconsistent: {e}"}, status=500)

    papers = [
        {
            "paper_id": r.get("paper_id"),
            "doi": r.get("doi"),
            "title": r.get("title"),
            "year": r.get("year"),
            "venue": r.get("venue"),
            "abstract": r.get("abstract"),
            "citation_count": r.get("citation_count"),
            "authors": json.loads(r["authors_json"]) if r.get("authors_json") else [],
        }
        for r in rows
    ]
    if query:
        papers = [p for p in papers if _paper_matches(p, query)]
    return JsonResponse(_payload(papers, len(rows)))


def _paper_matches(paper: dict, query: str) -> bool:
    """Case-insensitive substring match over the fields the UI shows.

    Authors arrive as names or objects depending on the MASTER record, so both
    shapes are flattened here rather than guessed at in the client.
    """
    authors = [
        a if isinstance(a, str) else (a or {}).get("name", "")
        for a in (paper.get("authors") or [])
    ]
    haystack = " ".join(
        str(part)
        for part in (
            paper.get("title"),
            paper.get("doi"),
            paper.get("venue"),
            paper.get("year"),
            paper.get("paper_id"),
            *authors,
        )
        if part is not None
    )
    return query.casefold() in haystack.casefold()


@require_POST
def library_enrich(request, _pipeline=None):
    """Enrich ONE library paper's metadata from the databases (#106).

    Body: {"paper_id": str, "force": bool}. Loads the master record, runs the
    package's enrichment engine, and writes the enriched metadata back to the
    same user-scoped library (no account required).

    `_pipeline` is a test-injection seam (PA-306: the collaborator is a
    parameter, not a monkeypatch). Django routes call it with only `request`
    (``_pipeline=None`` -> the real ScholarPipelineMetadataSingle); tests call
    the function directly with a deterministic, offline fake.
    """
    paper_id = (request.POST.get("paper_id") or "").strip()
    if not paper_id:
        return JsonResponse({"error": "paper_id required"}, status=400)
    force = (request.POST.get("force") or "").lower() in ("1", "true", "yes")

    root = _library_root_for(request)
    meta_path = root / "MASTER" / paper_id / "metadata.json"
    if not meta_path.is_file():
        return JsonResponse({"error": f"library paper not found: {paper_id}"}, status=404)

    try:
        paper = _load_library_paper(root, paper_id)

        if _pipeline is None:
            from scitex_scholar.pipelines.ScholarPipelineMetadataSingle import (
                ScholarPipelineMetadataSingle,
            )
            _pipeline = ScholarPipelineMetadataSingle()

        enriched = asyncio.run(_pipeline.enrich_paper_async(paper, force=force))
        _save_library_paper(enriched, root)

        m = enriched.metadata
        return JsonResponse(
            {
                "ok": True,
                "paper_id": paper_id,
                "doi": m.id.doi,
                "title": m.basic.title,
                "year": m.basic.year,
                "abstract_chars": len(m.basic.abstract or ""),
                "citation_count": m.citation_count.total,
            }
        )
    except Exception as e:
        logger.error(f"library enrich failed for {paper_id!r}: {e}", exc_info=True)
        return JsonResponse({"error": f"Enrichment failed: {e}"}, status=500)


# ---------------------------------------------------------------------------
# Library Import / Export (#106 / L327): the Library tab's Import/Export,
# thin adapters over the package's own BibTeX + formatting layer.
#
#   export -> formatting.papers_to_format (bibtex / ris / endnote) over the
#            user's local library rows (same collect_rows the list view reads)
#   import -> storage.BibTeXHandler.papers_from_bibtex, persisted to the SAME
#            MASTER/<paper_id>/metadata.json path the list/enrich routes use,
#            so an imported paper is immediately visible and enrichable.
#
# Format support is reported honestly: the formatter supports bibtex/ris/
# endnote for EXPORT; BibTeX is the supported IMPORT format (no RIS/CSL-JSON
# importer exists in the package, so those are not claimed).
# ---------------------------------------------------------------------------

LIBRARY_EXPORT_FORMATS = ("bibtex", "ris", "endnote")
LIBRARY_IMPORT_FORMATS = ("bibtex",)


def _row_to_formatting_dict(row: dict) -> dict:
    """Map a library index row to the dict shape papers_to_format expects.

    The bibtex/ris/endnote formatters read ``authors_str`` (a joined name
    string) -- NOT the ``authors`` list -- so both are supplied: ``authors``
    for consumers that want the structured list and ``authors_str`` so the
    export actually carries the author names (defect: it used to drop them).
    """
    import json as _json

    authors = row.get("authors_json")
    if authors:
        try:
            authors = _json.loads(authors)
        except (ValueError, TypeError):
            authors = []
    if not isinstance(authors, list):
        authors = []
    # The stored author is a name string (or {"name": ...}); join with " and "
    # -- the separator to_ris/to_endnote split on -- so multi-author exports
    # keep every author as a distinct entry.
    names = [a.get("name") if isinstance(a, dict) else str(a) for a in authors if a]
    authors_str = " and ".join(names)
    return {
        "title": row.get("title") or "",
        "authors": names,
        "authors_str": authors_str,
        "year": row.get("year"),
        "journal": row.get("venue"),
        "doi": row.get("doi"),
        "abstract": row.get("abstract"),
    }


@require_GET
def library_export(request):
    """Export the user's local library to bibtex / ris / endnote.

    ?format=bibtex|ris|endnote (default bibtex). Streams the serialized
    library as the response body with the right content type.
    """
    fmt = (request.GET.get("format") or "bibtex").strip().lower()
    if fmt not in LIBRARY_EXPORT_FORMATS:
        return JsonResponse(
            {
                "error": f"Unsupported export format: {fmt}",
                "supported": list(LIBRARY_EXPORT_FORMATS),
            },
            status=400,
        )

    root = _library_root_for(request)
    from scitex_scholar.formatting import papers_to_format
    from scitex_scholar.storage import _library_index as idx

    try:
        rows = idx.collect_rows(root)
    except FileNotFoundError:
        rows = []
    except ValueError as e:
        return JsonResponse({"error": f"Library inconsistent: {e}"}, status=500)

    try:
        content = papers_to_format([_row_to_formatting_dict(r) for r in rows], fmt)
    except Exception as e:
        logger.error(f"library export ({fmt}) failed: {e}", exc_info=True)
        return JsonResponse({"error": f"Export failed: {e}"}, status=500)

    content_type = {
        "bibtex": "application/x-bibtex",
        "ris": "application/x-research-info-systems",
        "endnote": "application/x-endnote-references",
    }[fmt]
    ext = {"bibtex": "bib", "ris": "ris", "endnote": "enw"}[fmt]
    resp = HttpResponse(content, content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="scholar-library.{ext}"'
    return resp


def _derived_library_id(paper) -> str:
    """Stable, dedup-friendly id for an imported paper.

    Reuses an existing library_id; otherwise derives one from the DOI (preferred)
    or title so re-importing the same paper does not create duplicates.
    """
    existing = getattr(paper.container, "library_id", None)
    if existing:
        return existing
    key = paper.metadata.id.doi or paper.metadata.basic.title or ""
    import hashlib

    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()


@require_POST
def library_import(request):
    """Import BibTeX into the user's local library.

    Body: format=bibtex (default) + bibtex=<bibliography text>. Each entry is
    parsed by the package's BibTeX handler and persisted to the same
    MASTER/<paper_id>/metadata.json path the list/enrich routes read, so imported
    papers are immediately visible and enrichable.
    """
    fmt = (request.POST.get("format") or "bibtex").strip().lower()
    if fmt not in LIBRARY_IMPORT_FORMATS:
        return JsonResponse(
            {
                "error": f"Unsupported import format: {fmt}",
                "supported": list(LIBRARY_IMPORT_FORMATS),
            },
            status=400,
        )
    bibtex_text = (request.POST.get("bibtex") or "").strip()
    if not bibtex_text:
        return JsonResponse({"error": "bibtex field required"}, status=400)

    root = _library_root_for(request)
    try:
        # Parse the POST body as BibTeX CONTENT, never as a file path. The
        # public papers_from_bibtex auto-detects path-vs-content and would READ
        # A SERVER FILE if the (untrusted) payload contained "/", "\\", "~",
        # or a leading "." -- so we call the text parser directly, bypassing
        # that detection. Importing ScholarLibrary registers the scitex_io
        # BibTeX loader the parser needs (a bare BibTeXHandler otherwise
        # parses 0 entries); the handler itself is config-independent for text.
        # (Defect 2.) The regression test (slash/backslash/path-like payloads)
        # proves no server file is read.
        import scitex_scholar.storage.ScholarLibrary  # noqa: F401 -- registers loader
        from scitex_scholar.storage.BibTeXHandler import BibTeXHandler

        papers = BibTeXHandler()._papers_from_bibtex_text(bibtex_text)
        if not papers:
            return JsonResponse(
                {"error": "No papers found in the provided BibTeX", "imported": 0},
                status=400,
            )

        imported = []
        for paper in papers:
            # Validate the id is a single safe path component BEFORE persisting,
            # so MASTER/<library_id> can never escape the library root.
            library_id = _assert_safe_library_id(_derived_library_id(paper))
            paper.container.library_id = library_id
            _save_library_paper(paper, root)
            imported.append(library_id)

        return JsonResponse({"ok": True, "imported": len(imported), "paper_ids": imported})
    except Exception as e:
        logger.error(f"library import failed: {e}", exc_info=True)
        return JsonResponse({"error": f"Import failed: {e}"}, status=500)


# EOF
