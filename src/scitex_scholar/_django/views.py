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
    from django.templatetags.static import static as _static_url
    from django.utils.translation import gettext as _i18n  # noqa: N816  (JS string dict)
    from django.views.decorators.http import (
        require_GET,
        require_POST,
        require_http_methods,
    )
except ImportError as exc:  # django absent -- the [all]-gated GUI capability only
    raise ImportError(
        "scitex_scholar._django.views needs Django, which is not installed. "
        "Install the optional stack: pip install 'scitex-scholar[all]'"
    ) from exc

try:
    from scitex_sdk.app.embed import mount_prefix
except ImportError as exc:  # scitex-sdk absent -- the [all]-gated GUI capability only
    raise ImportError(
        "scitex_scholar._django.views needs scitex-sdk, which is not "
        "installed. Install the optional stack: pip install 'scitex-scholar[all]'"
    ) from exc

try:
    from scitex_sdk.ui.branding import shell_context
except ImportError as exc:  # scitex-sdk absent or below the GUI capability floor
    raise ImportError(
        "scitex_scholar._django.views needs scitex-sdk>=0.3.1. "
        "Install the optional stack: pip install 'scitex-scholar[all]'"
    ) from exc

try:
    from scitex_sdk.ui.project_scope import (
        LocalProjectProvider,
        host_project_provider,
        resolve_project,
        scoped_project_listing_view,
    )
except ImportError as exc:  # scitex-sdk absent -- the [all]-gated GUI capability only
    raise ImportError(
        "scitex_scholar._django.views needs scitex-sdk, which is not "
        "installed. Install the optional stack: pip install 'scitex-scholar[all]'"
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

# Simple in-memory cache (framework-agnostic, ported verbatim, then capped).
#
# The cap is load-bearing on a mounted host: one server process serves many
# users x queries, and without eviction every distinct query accumulates for
# the TTL hour (measured: 3000 sets -> 3000 live entries, expired rows kept
# until re-accessed). 500 entries x a result payload is ample for a GUI cache
# and keeps per-process memory flat. Eviction is insertion-order (oldest
# first); a hit refreshes recency via re-insertion.
_cache: Dict[str, dict] = {}
_cache_timestamps: Dict[str, float] = {}
_CACHE_TTL = 3600  # 1 hour
_CACHE_MAX_ENTRIES = 500


def _cache_get(key: str) -> Optional[dict]:
    """Get value from cache if not expired."""
    if key in _cache:
        if time.time() - _cache_timestamps.get(key, 0) < _CACHE_TTL:
            # Refresh recency so live entries survive eviction pressure.
            _cache[key] = _cache.pop(key)
            return _cache[key]
        del _cache[key]
        del _cache_timestamps[key]
    return None


def _cache_set(key: str, value: dict, ttl: int = _CACHE_TTL):
    """Set value in cache, evicting oldest entries past the cap."""
    if key in _cache:
        del _cache[key]
    _cache[key] = value
    _cache_timestamps[key] = time.time()
    while len(_cache) > _CACHE_MAX_ENTRIES:
        oldest, _ = next(iter(_cache.items()))
        del _cache[oldest]
        _cache_timestamps.pop(oldest, None)


def _cache_scope(request) -> str:
    """The cache partition a request's payloads belong to.

    The mounted per-user library roots mean the same query from two users
    is NOT the same answer: a process-wide cache keyed on query alone
    serves one user's payload to another. Partition on the request user so
    each identity (and anonymous) has its own cache lane.
    """
    user = getattr(request, "user", None)
    name = getattr(user, "username", None)
    if not name and getattr(user, "is_authenticated", False):
        name = str(getattr(user, "pk", "") or "user")
    return f"user:{name}" if name else "anon"


def _make_cache_key(prefix: str, doi: str, scope: str = "", **kwargs) -> str:
    """Create cache key from parameters."""
    parts = [prefix, scope, doi.lower()]
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
    """The 'no crossref-local endpoint' body, with the fix in it.

    All user-facing strings go through gettext so the Service Status
    sidebar paragraph renders JA under a JA locale instead of staying
    English (operator screenshot 2026-10-16). The setting name travels
    as a %(setting)s placeholder so the msgid stays stable.
    """
    return {
        "error": _i18n("CrossRef API not configured"),
        "detail": _i18n(
            "The citation graph reads its data from a citation-data HTTP API. "
            "No endpoint is configured, so there is nothing to query."
        ),
        "fix": _i18n(
            "Set %(setting)s to a running crossref-local endpoint (env var of "
            "the same name, or the Django setting when scholar is mounted in "
            "a host project), then restart the server. Installing the "
            "`crossref-local` package supplies a default endpoint, which "
            "scholar falls back to when the variable is unset."
        )
        % {"setting": CROSSREF_API_URL_SETTING},
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
    except ImportError as exc:  # django absent -- the [all]-gated GUI capability only
        raise ImportError(
            "scitex_scholar._django.views needs Django, which is not "
            "installed. Install the optional stack: "
            "pip install 'scitex-scholar[all]'"
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
    """scitex-sdk's standalone provider, minus the library's reserved dirs.

    scitex-sdk's ::class:`LocalProjectProvider` treats EVERY non-hidden folder
    under its root as a selectable project. Scholar's standalone root IS the
    library root, whose direct children also include ``MASTER/`` (the
    deduplicated paper store) and ``downloads/`` (the PDF staging area), so the
    stock provider offered the internal store as if it were a user project.

    Subclassing (rather than reimplementing) keeps scitex-sdk authoritative for
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
            # Case-insensitive: the primary-store folder is the same internal store on
            # a case-insensitive filesystem, and MUST NOT slip through here.
            if entry.name.upper() not in reserved
            and not (self.root / entry.name).is_symlink()
        ]


    def user_scope_disabled_reason(self, request=None):
        """All stays available in Scholar: no reason to disable user scope.

        The SDK's scoped listing view (0.3.16, PR #90) consults this
        optional hook only on a scoped provider. This hook is dormant
        standalone -- the local provider is unscoped, so the view answers
        the legacy shape (``allow_user_scope: false``, no tagged scope)
        and never calls it. It becomes live when mounted, because
        ``_project_provider`` delegates to the host provider there and the
        view consults the HOST provider's hook, not this one.
        """
        return None


def _project_provider(request):
    """Use the mounted host provider, or scitex-sdk's local provider standalone."""
    return host_project_provider() or ScholarLocalProjectProvider(
        _standalone_projects_root()
    )


# Shared scitex-sdk GET-list / POST-remember endpoint (SDK 0.3.16 scoped view,
# PR #90). The provider factory is request-time so mounted hosts remain
# authoritative for permissions and project identity; Scholar contains no Hub
# model or authorization logic. The scoped view guarantees the legacy
# byte-compatible shape when the resolved provider is unscoped (standalone
# local provider: no current_scope, legacy POST {id} only), and adds the
# tagged {scope, id} contract when mounted behind a scoped host provider.
project_scope = scoped_project_listing_view(_project_provider)


def _leaf_identity() -> dict:
    """Title + version for the leaf header, read from the leaf's own dist.

    Mirrors writer's `_leaf_identity` in SHAPE (operator header mandate
    2026-10-17: `<title> + v<version>`) while reading the version from the
    package's own `__version__` (importlib.metadata, stdlib-only) instead of
    the app registry: the same installed-version source the SDK's
    `app_version` resolves, with no new imports and no registry dependency.
    Never a hand-written string and never the host's version.
    """
    from scitex_scholar import __version__

    return {"scholar_version": __version__}


def index_context(request, current_project=None):
    """Return the existing Scholar page context for this request."""
    resolved_api = _api_url()
    provider = _project_provider(request)
    current_project = resolve_project(
        request,
        provider,
        explicit=request.GET.get("project"),
    )
    # The SDK picker tag needs the EXPLICIT selection state: a user-scoped
    # app (app_scope "user") opts into the picker with allow_user_scope, and
    # current_scope tells it whether a project is selected. An absent
    # selection is explicit user scope, never an implied project.
    current_scope = "project" if current_project else "user"
    return {
        **shell_context("Scholar", theme_default="light"),
        **_leaf_identity(),
        "api_available": resolved_api is not None,
        "api_url": resolved_api or "Not configured",
        "stx_mount": mount_prefix(request),
        "app_label": _app_label("Scholar"),
        "app_scope": "user",
        # Operator 2026-10-23: the tab icon is the official mark (white
        # snake on navy), no dev/prod switching. The installed SDK SSOT
        # (0.3.12) still serves the retired green snake; the official mark
        # exists only in SDK develop (unreleased). SUNSET: drop this
        # override + the file once the installed SDK serves the official
        # mark, and pin that SDK floor in pyproject.toml. Provenance: byte
        # copy of SDK develop's scitex-favicon.svg (same snake artwork).
        "favicon_href": _static_url("scholar/img/scitex-favicon-official.svg"),
        "current_project": current_project,
        "current_scope": current_scope,
        # i18n (operator directive 2026-09-14): the whole page flips via
        # LocaleMiddleware; this carries the strings that live ONLY in
        # JS, translated server-side for the current request language so
        # the client never hardcodes a language. Serialized by the
        # template's json_script filter into <script id="SCHOLAR_I18N">;
        # the client reads it via JSON.parse (see scholarT in stx-mount.js).
        "scholar_i18n": _js_i18n_dict(),
        # The scitex-sdk workspace shell renders three side panes
        # (Console/Chat, Files, Viewer) around the app content. Scholar
        # has no content for them, and because the template extends the
        # shell directly (it is not a built SPA shell the SDK wraps) they
        # would otherwise render empty — the large left gutter on desktop
        # and the broken reflow on mobile. Declare them unused so the
        # shell hides them and Scholar is the whole page. This is the
        # shell's documented contract ("panes ... DECLARED by the app").
        "panes": {"ai": "unused", "files": "unused", "viewer": "unused"},
    }


def render_workspace_content(request, current_project=None, *, stx_mount):
    """Render the existing workspace content at the host-verified app root."""
    context = index_context(request, current_project)
    context["stx_mount"] = stx_mount.rstrip("/")
    html = render_to_string(
        "scholar/workspace_renderer.html",
        context,
        request=request,
    )
    return HttpResponse(html)


def index(request):
    """Serve the Scholar SPA shell page.

    `favicon_href` carries the official SciTeX mark (white snake on navy,
    operator 2026-10-23): the shared branding partial honours the var, so
    the leaf supplies its own file through the contract rather than
    shadowing the partial with an inline icon. SUNSET: drop the override
    once the installed SDK SSOT serves the official mark.
    """
    html = render_to_string(
        "scholar/scholar.html",
        index_context(request),
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
        # Search tab slice 1 (old-direct unification): an explicit Sources
        # selection reports itself in the results header -- same catalog
        # visibility rule as the tier strings above.
        "Selected sources": _i18n("Selected sources"),
        "Imported %(n)s paper from %(file)s": _i18n("Imported %(n)s paper from %(file)s"),
        "Imported %(n)s papers from %(file)s": _i18n("Imported %(n)s papers from %(file)s"),
        # Search tab slice 2 (old-direct parity): per-result Save and the
        # bulk/pipeline pills render these client-side, so each MUST be a
        # key here -- an English literal in search.js is invisible to the
        # catalog and shows EN on a JA page.
        "Save": _i18n("Save"),
        "Saving…": _i18n("Saving…"),
        "Saved": _i18n("Saved"),
        "Save failed": _i18n("Save failed"),
        # Brief-05: the Graph seed pills render client-side -- same rule.
        "Graph": _i18n("Graph"),
        "Select results with a DOI first.": _i18n("Select results with a DOI first."),
        # Catch-up: node sheet actions render client-side -- same rule.
        "Add to library": _i18n("Add to library"),
        "Explore from here": _i18n("Explore from here"),
        "Select results to save.": _i18n("Select results to save."),
        "Saved %(saved)s of %(total)s": _i18n("Saved %(saved)s of %(total)s"),
        "Enriched %(done)s of %(total)s": _i18n("Enriched %(done)s of %(total)s"),
        # Search tab slice 3 (old-direct unification): the results-header
        # tools render these client-side -- same catalog-visibility rule.
        "Abstract: truncated": _i18n("Abstract: truncated"),
        "Abstract: full": _i18n("Abstract: full"),
        "Select results first.": _i18n("Select results first."),
        "No DOI links in selection.": _i18n("No DOI links in selection."),
        "Copied %(n)s BibTeX entry": _i18n("Copied %(n)s BibTeX entry"),
        "Copied %(n)s BibTeX entries": _i18n("Copied %(n)s BibTeX entries"),
        "Copy failed": _i18n("Copy failed"),
        # Library tab slice 4b (old-direct unification): the per-row
        # details panel renders these client-side -- same rule.
        "To read": _i18n("To read"),
        "Reading": _i18n("Reading"),
        "Read": _i18n("Read"),
        "Referenced": _i18n("Referenced"),
        "Favorite": _i18n("Favorite"),
        "Reading status": _i18n("Reading status"),
        "Importance": _i18n("Importance"),
        "Tags": _i18n("Tags"),
        "Add tag...": _i18n("Add tag..."),
        "Personal notes": _i18n("Personal notes"),
        "Add your notes about this paper...": _i18n(
            "Add your notes about this paper..."
        ),
        "Save changes": _i18n("Save changes"),
        "Details": _i18n("Details"),
        # Library tab slice 5 (old-direct unification): the import
        # preview panel renders these client-side -- same rule.
        "Previewing %(file)s…": _i18n("Previewing %(file)s…"),
        "Previewing %(n)s paper from %(file)s": _i18n(
            "Previewing %(n)s paper from %(file)s"
        ),
        "Previewing %(n)s papers from %(file)s": _i18n(
            "Previewing %(n)s papers from %(file)s"
        ),
        "Importing %(file)s…": _i18n("Importing %(file)s…"),
        "Already in library": _i18n("Already in library"),
        # Graph tab slice 9 (old-direct unification): the saved-graphs
        # card renders these client-side -- same rule.
        "No saved graphs yet.": _i18n("No saved graphs yet."),
        "Load": _i18n("Load"),
        "Delete": _i18n("Delete"),
        "Name the graph and build it first.": _i18n("Name the graph and build it first."),
        "Graph saved": _i18n("Graph saved"),
        "Graph not found": _i18n("Graph not found"),
        "Graph deleted": _i18n("Graph deleted"),
        "Delete failed": _i18n("Delete failed"),
        # Library tab slice 10 (old-direct unification): the details
        # remove action renders client-side -- same rule.
        "Remove from library": _i18n("Remove from library"),
        "Remove this paper from the library?": _i18n(
            "Remove this paper from the library?"
        ),
        "Remove failed": _i18n("Remove failed"),
        # Graph tab slice 10: the saved-list rename action -- same rule.
        "Rename": _i18n("Rename"),
        "Graph renamed": _i18n("Graph renamed"),
        "Rename failed": _i18n("Rename failed"),
        # Brief-05: Graph Library multi-seed builds, two-click delete,
        # save-count -- same rule.
        "Build a single-seed graph first.": _i18n("Build a single-seed graph first."),
        "Confirm delete?": _i18n("Confirm delete?"),
        "%(n)s saved": _i18n("%(n)s saved"),
        # Search tab slice 11 (old-direct unification): the PDFs bulk
        # pill + Library details download button -- same rule. Server
        # per-item errors render through scholarT too, so they are keys.
        "Download PDF": _i18n("Download PDF"),
        "PDF downloaded": _i18n("PDF downloaded"),
        "Download failed": _i18n("Download failed"),
        "Downloaded %(done)s of %(total)s PDFs": _i18n(
            "Downloaded %(done)s of %(total)s PDFs"
        ),
        "No open-access PDF available": _i18n("No open-access PDF available"),
        "Paper not found": _i18n("Paper not found"),
        "Load failed. Try again later.": _i18n("Load failed. Try again later."),
        # Library pane hardening (apps-lead probe 2026-10-22): an
        # expired/missing credential is 302'd to the hub login page, so
        # the pane gets HTML where JSON was expected. The client turns
        # that shape into a re-login prompt, not a SyntaxError; other
        # non-JSON bodies keep the status-surfaced error.
        "Session expired. Please log in again.": _i18n(
            "Session expired. Please log in again."
        ),
        "Server returned non-JSON (status %(status)s)": _i18n(
            "Server returned non-JSON (status %(status)s)"
        ),
        "Download failed. Try again later.": _i18n("Download failed. Try again later."),
        # Old-direct U7: the node sheet close button renders client-side,
        # so it MUST be a key here (same catalog-visibility rule).
        "Close": _i18n("Close"),
        # Graph tab slice 3a (old-direct parity): the library-seed picker
        # renders these client-side, so each MUST be a key here -- an
        # English literal in citation-graph.js is invisible to the catalog
        # and shows EN on a JA page.
        "Seed from your Library": _i18n("Seed from your Library"),
        "Loading your library…": _i18n("Loading your library…"),
        "No papers with a DOI in your library yet.": _i18n(
            "No papers with a DOI in your library yet."
        ),
        # Library tab slice 3b (old-direct parity): the Zotero /
        # Connected Papers import controls render these client-side, so
        # each MUST be a key here for the same catalog-visibility reason.
        "Importing…": _i18n("Importing…"),
        "Import failed": _i18n("Import failed"),
        "Zotero database found": _i18n("Zotero database found"),
        "Zotero database not found": _i18n("Zotero database not found"),
        "Connected Papers available": _i18n("Connected Papers available"),
        "Connected Papers unavailable": _i18n("Connected Papers unavailable"),
        "Imported %(imported)s of %(total)s papers": _i18n(
            "Imported %(imported)s of %(total)s papers"
        ),
        "Enter a Semantic Scholar paper ID": _i18n(
            "Enter a Semantic Scholar paper ID"
        ),
        # Library tab slice 3c (old-direct parity): the project sync
        # indicator/chips render these client-side, so each MUST be a
        # key here for the same catalog-visibility reason.
        "Project": _i18n("Project"),
        "All projects": _i18n("All projects"),
        "Project: %(project)s": _i18n("Project: %(project)s"),
        # Error fallback (UX standard): the retry buttons on all three
        # surfaces and the graph seed picker render client-side.
        "Retry": _i18n("Retry"),
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

    # The body reports STATE (api_available), never the endpoint ADDRESS:
    # the raw crossref-local URL names server infrastructure, which is not
    # a client concern (same disclosure class as the graph_health `api_url`
    # leak and the library_root list payload). No JS or template reads this
    # key; api_available already answers the configured question.
    return JsonResponse(
        {
            "status": "ok",
            "version": __version__,
            "api_available": _api_url() is not None,
        }
    )


@require_GET
def graph_network(request, _builder=None):
    """Build citation network for a DOI.

    `_builder` is a test-injection seam: the collaborator is a PARAMETER,
    not a monkeypatch (PA-306), exactly as `search(request, _engine=)`.
    Django routes call it with only `request`.
    """
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)
    if len(doi) > _MAX_DOI_CHARS:
        return _overlong_doi_response()

    try:
        top_n = int(request.GET.get("top_n", 20))
        top_n = max(1, min(50, top_n))
        weight_coupling = float(request.GET.get("weight_coupling", 2.0))
        weight_cocitation = float(request.GET.get("weight_cocitation", 2.0))
        weight_direct = float(request.GET.get("weight_direct", 1.0))
    except ValueError:
        return JsonResponse(
            {
                "error": (
                    "top_n, weight_coupling, weight_cocitation, and "
                    "weight_direct must be numbers"
                )
            },
            status=400,
        )

    use_cache = request.GET.get("no_cache", "false").lower() != "true"

    # Check cache
    cache_key = _make_cache_key(
        "net",
        doi,
        _cache_scope(request),
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
    builder = _builder or _get_builder()
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
        return JsonResponse({"error": "Failed to build network. Try again later."}, status=500)


#: Largest accepted seed count on the multi-seed graph build (hub parity:
#: hub allows 20 DOIs; each fans out to related-paper discovery, so an
#: unbounded list is per-request graph + cache pressure).
_MAX_GRAPH_SEEDS = 20


@require_GET
def graph_network_multi(request, _builder=None):
    """Build a citation network from multiple seed DOIs (hub parity).

    ?dois=a,b,c (required, at most 20) + num_related_per_doi (default 20,
    capped at 50, hub parity) + the shared weights/no_cache. Hub wires no
    UI to its multi endpoint either; this is API parity over the existing
    builder, same validation/cache/error class as graph_network.

    `_builder` is a test-injection seam (PA-306).
    """
    dois_raw = (request.GET.get("dois") or "").strip()
    if not dois_raw:
        return JsonResponse(
            {"error": "dois parameter required (comma-separated DOIs)"}, status=400
        )
    dois = [d.strip() for d in dois_raw.split(",") if d.strip()]
    if not dois:
        return JsonResponse({"error": "At least one DOI required"}, status=400)
    if len(dois) > _MAX_GRAPH_SEEDS:
        return JsonResponse(
            {"error": f"At most {_MAX_GRAPH_SEEDS} DOIs allowed"}, status=400
        )
    if any(len(d) > _MAX_DOI_CHARS for d in dois):
        return _overlong_doi_response()

    try:
        num_related = int(request.GET.get("num_related_per_doi", 20))
        num_related = max(1, min(num_related, 50))
        weight_coupling = float(request.GET.get("weight_coupling", 2.0))
        weight_cocitation = float(request.GET.get("weight_cocitation", 2.0))
        weight_direct = float(request.GET.get("weight_direct", 1.0))
    except ValueError:
        return JsonResponse(
            {
                "error": (
                    "num_related_per_doi, weight_coupling, weight_cocitation, and "
                    "weight_direct must be numbers"
                )
            },
            status=400,
        )

    use_cache = request.GET.get("no_cache", "false").lower() != "true"

    cache_key = _make_cache_key(
        "net-multi",
        ",".join(sorted(d.lower() for d in dois)),
        _cache_scope(request),
        num_related=num_related,
        wc=weight_coupling,
        wco=weight_cocitation,
        wd=weight_direct,
    )
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            cached["metadata"]["cached"] = True
            return JsonResponse(cached)

    builder = _builder or _get_builder()
    if not builder:
        return JsonResponse(_not_configured_payload(), status=503)

    try:
        graph = builder.build_from_dois(
            dois=dois,
            num_related_per_doi=num_related,
            weight_coupling=weight_coupling,
            weight_cocitation=weight_cocitation,
            weight_direct=weight_direct,
        )
        result = graph.to_dict()
        result["metadata"]["cached"] = False

        seeds = {d.lower() for d in dois}
        for node in result["nodes"]:
            node["is_seed"] = node["id"].lower() in seeds

        _cache_set(cache_key, result)
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error building multi-seed network: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to build network. Try again later."}, status=500)


@require_GET
def graph_network_query(request, _builder=None):
    """Build a citation network from a text query (hub parity).

    ?q= (required, capped like the search query) + num_related_per_doi +
    the shared weights/no_cache. Same class as graph_network_multi above.

    `_builder` is a test-injection seam (PA-306).
    """
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"error": "q parameter required"}, status=400)
    if len(query) > _MAX_QUERY_CHARS:
        return JsonResponse(
            {"error": f"q must be at most {_MAX_QUERY_CHARS} characters"},
            status=400,
        )

    try:
        num_related = int(request.GET.get("num_related_per_doi", 20))
        num_related = max(1, min(num_related, 50))
        weight_coupling = float(request.GET.get("weight_coupling", 2.0))
        weight_cocitation = float(request.GET.get("weight_cocitation", 2.0))
        weight_direct = float(request.GET.get("weight_direct", 1.0))
    except ValueError:
        return JsonResponse(
            {
                "error": (
                    "num_related_per_doi, weight_coupling, weight_cocitation, and "
                    "weight_direct must be numbers"
                )
            },
            status=400,
        )

    use_cache = request.GET.get("no_cache", "false").lower() != "true"

    cache_key = _make_cache_key(
        "net-query",
        query,
        _cache_scope(request),
        num_related=num_related,
        wc=weight_coupling,
        wco=weight_cocitation,
        wd=weight_direct,
    )
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            cached["metadata"]["cached"] = True
            return JsonResponse(cached)

    builder = _builder or _get_builder()
    if not builder:
        return JsonResponse(_not_configured_payload(), status=503)

    try:
        graph = builder.build_from_query(
            query=query,
            num_related_per_doi=num_related,
            weight_coupling=weight_coupling,
            weight_cocitation=weight_cocitation,
            weight_direct=weight_direct,
        )
        result = graph.to_dict()
        result["metadata"]["cached"] = False

        _cache_set(cache_key, result)
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error building query network for {query!r}: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to build network. Try again later."}, status=500)


@require_GET
def graph_related(request, _builder=None):
    """Get related papers for a DOI.

    `_builder` is a test-injection seam: the collaborator is a PARAMETER,
    not a monkeypatch (PA-306), exactly as `search(request, _engine=)`.
    Django routes call it with only `request`.
    """
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)
    if len(doi) > _MAX_DOI_CHARS:
        return _overlong_doi_response()

    try:
        limit = int(request.GET.get("limit", 10))
        limit = max(1, min(30, limit))
    except ValueError:
        return JsonResponse(
            {"error": "limit must be an integer"}, status=400
        )

    builder = _builder or _get_builder()
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

        # The success body carries the server-computed result only (related +
        # count), never the caller-supplied doi back whole: a 200 body must
        # not round-trip untrusted input (same reflection class as the
        # saved-searches save/delete echoes). The only client
        # (citation-graph.js) reads data.related; nothing reads the doi key.
        return JsonResponse({"related": related, "count": len(related)})

    except Exception as e:
        logger.error(f"Error getting related papers for {doi}: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to get related papers. Try again later."}, status=500)


@require_GET
def graph_paper(request, _builder=None):
    """Get paper summary.

    `_builder` is a test-injection seam: the collaborator is a PARAMETER,
    not a monkeypatch (PA-306), exactly as `search(request, _engine=)`.
    Django routes call it with only `request`.
    """
    doi = request.GET.get("doi")
    if not doi:
        return JsonResponse({"error": "DOI parameter required"}, status=400)
    if len(doi) > _MAX_DOI_CHARS:
        return _overlong_doi_response()

    builder = _builder or _get_builder()
    if not builder:
        return JsonResponse(_not_configured_payload(), status=503)

    try:
        summary = builder.get_paper_summary(doi)
        if summary:
            return JsonResponse(summary)
        return JsonResponse({"error": "Paper not found"}, status=404)

    except Exception as e:
        logger.error(f"Error getting paper summary for {doi}: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to get paper summary. Try again later."}, status=500)


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
                "error": _i18n("Citation Graph: not checked"),
                "detail": _i18n(
                    "A citation-data endpoint is configured. The graph backend "
                    "is checked when you open the Citation Graph tab, so a slow "
                    "or unreachable service cannot delay the rest of the page."
                ),
                "fix": _i18n("Open the Citation Graph tab to check it."),
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
                "error": _i18n("Citation Graph: unavailable"),
                "detail": _i18n(
                    "The citation-data endpoint is configured but could not "
                    "be reached right now, so citation graphs cannot be built."
                ),
                "fix": _i18n(
                    "The citation service may be temporarily down — wait a "
                    "moment and retry by opening the Citation Graph tab."
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
        "error": _i18n("Citation Graph: limited"),
        "detail": _i18n(
            "The citation-data endpoint is configured and reachable, but the "
            "check returned no data for the sample paper. Citation graphs may "
            "be incomplete."
        ),
        "fix": _i18n(
            "Check that the citation-data endpoint is serving the corpus you "
            "expect; the citation graph depends on it."
        ),
    }


def _strip_markup_from_search_abstracts(result: dict) -> None:
    """Strip JATS/HTML markup from live-search abstracts, in place.

    WHY (CCT 2759/2760, 2026-10-15): EuropePMC/PMC abstracts arrive with
    raw JATS XML tags (e.g. ``<jats:p>``); the leaf served them verbatim
    and the client renders via textContent, so researchers saw raw markup.
    The package already owns ``TextNormalizer.strip_html_tags`` (also the
    metadata-enrichment choke point); the live-search path never funnels
    through it, so the leaf view strips at its own serialization boundary
    instead. Only non-empty str abstracts are touched; None/missing pass
    through untouched.
    """
    from scitex_scholar._utils.text import TextNormalizer

    for row in result.get("results") or []:
        if isinstance(row, dict):
            abstract = row.get("abstract")
            if isinstance(abstract, str) and abstract:
                row["abstract"] = TextNormalizer.strip_html_tags(abstract)


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
    if len(query) > _MAX_QUERY_CHARS:
        return JsonResponse(
            {"error": f"q must be at most {_MAX_QUERY_CHARS} characters"},
            status=400,
        )

    try:
        max_results = int(request.GET.get("max_results", 50))
        max_results = max(1, min(500, max_results))
    except ValueError:
        return JsonResponse(
            {"error": "max_results must be an integer"}, status=400
        )

    mode = request.GET.get("mode", "parallel")
    if mode not in ("parallel", "single"):
        return JsonResponse(
            {"error": "mode must be 'parallel' or 'single'"}, status=400
        )

    # Explicit source selection (old-direct Sources grid, hub `?sources=a,b,c`).
    # Unknown names are dropped, never a 400; an empty/all-unknown selection
    # keeps the tiered default. The raw string rides the cache key so two
    # different selections never share a cached result set.
    from scitex_scholar.search_engines._source_tiers import normalize_sources

    sources_raw = (request.GET.get("sources", "") or "").strip()
    if len(sources_raw) > _MAX_SOURCES_CHARS:
        return JsonResponse(
            {"error": f"sources must be at most {_MAX_SOURCES_CHARS} characters"},
            status=400,
        )
    sources = normalize_sources(sources_raw) if sources_raw else None

    # Explicit range filters (old-direct Filters sliders, hub hidden-input
    # names). Malformed numbers and inverted ranges fail closed (400), the
    # same convention as max_results/mode above.
    range_filters, range_error = _parse_range_filters(request.GET)
    if range_error:
        return JsonResponse({"error": range_error}, status=400)

    use_cache = request.GET.get("no_cache", "false").lower() != "true"
    cache_key = _make_cache_key(
        "search",
        query,
        _cache_scope(request),
        mode=mode,
        max_results=max_results,
        sources=",".join(sources) if sources else "",
        filters=json.dumps(range_filters, sort_keys=True) if range_filters else "",
    )
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            cached["metadata"]["cached"] = True
            return JsonResponse(cached)

    try:
        engine = _engine or _get_search_engine()
        # Old-direct U2: bind the pipeline progress callback. Last-wins
        # per engine, first-seen order -- the queue panel renders exactly
        # this list. Sync callback on a same-thread run; nothing escapes
        # the request, so search behavior is unchanged.
        engine_events = {}

        def _collect_progress(engine_name, status, count):
            engine_events[engine_name] = {
                "engine": engine_name,
                "status": status,
                "count": count,
            }

        result = asyncio.run(
            engine.search(
                query=query,
                mode=mode,
                max_results=max_results,
                sources=sources,
                filters=range_filters,
                on_progress=_collect_progress,
            )
        )
        _strip_markup_from_search_abstracts(result)
        result.setdefault("metadata", {})["cached"] = False
        result["metadata"]["engine_events"] = list(engine_events.values())
        if sources:
            result["metadata"]["sources_selected"] = sources
        _cache_set(cache_key, result)
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Search failed for {query!r}: {e}", exc_info=True)
        return JsonResponse({"error": "Search failed. Try again later."}, status=500)


@require_GET
def search_syntax_help(request):
    """Search syntax documentation (old-direct U1 unification).

    KEEP: the hub `api_search_syntax_help` document, verbatim -- status,
    operator flags, examples, sources, query parameters. Static JSON: no
    engine, no cache, no search behavior change (this view never calls
    the `search` view or the search engine).
    """
    return JsonResponse(
        {
            "status": "success",
            "syntax": {
                "title_filter": {
                    "short": "-t",
                    "long": "--title",
                    "description": "Filter by title content",
                    "include_example": "-t neural",
                    "exclude_example": "-t -mouse",
                },
                "author_filter": {
                    "short": "-a",
                    "long": "--author",
                    "description": "Filter by author name",
                    "include_example": "-a Smith",
                    "exclude_example": "-a -Jones",
                },
                "journal_filter": {
                    "short": "-j",
                    "long": "--journal",
                    "description": "Filter by journal name",
                    "include_example": "-j Nature",
                    "exclude_example": "-j -arXiv",
                },
                "year_min": {
                    "short": "-ymin",
                    "long": "--year-min",
                    "description": "Minimum publication year",
                    "example": "-ymin 2020",
                },
                "year_max": {
                    "short": "-ymax",
                    "long": "--year-max",
                    "description": "Maximum publication year",
                    "example": "-ymax 2024",
                },
                "citations_min": {
                    "short": "-cmin",
                    "long": "--citations-min",
                    "description": "Minimum citation count",
                    "example": "-cmin 100",
                },
                "citations_max": {
                    "short": "-cmax",
                    "long": "--citations-max",
                    "description": "Maximum citation count",
                    "example": "-cmax 1000",
                },
                "impact_factor_min": {
                    "short": "-ifmin",
                    "long": "--if-min",
                    "description": "Minimum journal impact factor",
                    "example": "-ifmin 5",
                },
                "impact_factor_max": {
                    "short": "-ifmax",
                    "long": "--if-max",
                    "description": "Maximum journal impact factor",
                    "example": "-ifmax 50",
                },
            },
            "examples": [
                {
                    "query": "neural network -t deep learning -ymin 2020",
                    "description": "Search for 'neural network', title must contain 'deep learning', published since 2020",
                },
                {
                    "query": "CRISPR -a Doudna -j Nature -cmin 100",
                    "description": "Search for 'CRISPR' by author Doudna in Nature journal with at least 100 citations",
                },
                {
                    "query": "cancer treatment -t -mouse -t -rat -ymin 2022",
                    "description": "Search for 'cancer treatment', exclude mouse and rat studies, since 2022",
                },
                {
                    "query": "machine learning -ifmin 10 -cmin 50",
                    "description": "Search 'machine learning' in journals with IF >= 10 and papers with >= 50 citations",
                },
            ],
            "available_sources": [
                "pubmed",
                "arxiv",
                "semantic",
                "crossref",
                "openalex",
                "pmc",
                "doaj",
                "biorxiv",
                "plos",
            ],
            "query_parameters": {
                "q": "Search query with optional command syntax (required)",
                "sources": "Comma-separated list of sources to search (optional)",
                "max_results": "Maximum results per source, 1-500 (default: 50)",
                "format": "'full' or 'compact' response format (default: full)",
            },
        }
    )


# ---------------------------------------------------------------------------
# Library API (#106: metadata enrichment as a contextual Library operation).
#
# Thin HTTP adapters over the package's own storage and enrichment layer --
# the same code the `scitex-scholar library` CLI drives. No library or
# enrichment logic lives in these views:
#   list  -> storage._library_index (user's local library index)
#   enrich-> storage.PaperIO (primary metadata.json) +
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


#: Largest accepted search query on the live search endpoint, the library
#: list filter, and the saved-search name/query fields. The rows file behind
#: saved searches is re-read whole per list call, the library filter casefolds
#: per row, and the live query fans out to the search engines and the result
#: cache key -- so an unbounded value is per-request engine + cache pressure.
#: 2k chars is far past any real query.
_MAX_QUERY_CHARS = 2000

#: Largest accepted JSON body on the write endpoints (save/save-bulk,
#: searches save+delete, enrich, import). Bodies parse whole before any
#: check, so an unbounded body is memory + disk pressure per request; 256k
#: is far past any legitimate payload (a paper abstract is bytes-to-low-kb,
#: bulk stays usable for 100+ papers).
_MAX_JSON_BODY_BYTES = 256 * 1024

#: Largest accepted save-bulk batch and BibTeX import. Both loops do one file
#: write per item, so an unbounded list is write amplification per request
#: even under the body-bytes cap (~1000 tiny papers fit in 256k); 500 items
#: is far past the documented 100+ legitimate bulk use.
_MAX_BULK_ITEMS = 500

#: Largest accepted DOI on the three graph endpoints. The value fans out to
#: the cache key, the graph builder, and the error log -- so an unbounded
#: value is per-request cache + engine + log pressure; 500 chars is far past
#: any real DOI (tens of chars).
_MAX_DOI_CHARS = 500

#: Largest accepted `sources` selection on the live search endpoint (hub
#: `?sources=a,b,c`). Same fan-out class as _MAX_DOI_CHARS (cache key +
#: engine fan-out); 500 chars is far past the seven known names (~80 chars).
_MAX_SOURCES_CHARS = 500

#: Bounds for the explicit range filters (old-direct Filters section, hub
#: hidden-input names). A bound outside these is a client bug, not a search.
_MIN_FILTER_YEAR = 1000
_MAX_FILTER_YEAR = 2100
_MAX_FILTER_CITATIONS = 100_000_000
_MAX_FILTER_IMPACT_FACTOR = 1000.0


def _parse_range_filters(params) -> tuple:
    """Map hub range params to pipeline threshold keys.

    Returns (filters_or_None, error_or_None). Empty strings count as
    absent; malformed numbers, out-of-range values, and inverted ranges
    return an error message for the view to fail closed with (400).
    """
    int_bounds = {
        "year_from": ("min_year", _MIN_FILTER_YEAR, _MAX_FILTER_YEAR),
        "year_to": ("max_year", _MIN_FILTER_YEAR, _MAX_FILTER_YEAR),
        "min_citations": ("min_citations", 0, _MAX_FILTER_CITATIONS),
        "max_citations": ("max_citations", 0, _MAX_FILTER_CITATIONS),
    }
    float_bounds = {
        "min_impact_factor": ("min_impact_factor", 0.0, _MAX_FILTER_IMPACT_FACTOR),
        "max_impact_factor": ("max_impact_factor", 0.0, _MAX_FILTER_IMPACT_FACTOR),
    }
    filters: dict = {}
    for name, (key, lo, hi) in int_bounds.items():
        raw = (params.get(name, "") or "").strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            return None, f"{name} must be an integer"
        if not lo <= value <= hi:
            return None, f"{name} must be between {lo} and {hi}"
        filters[key] = value
    for name, (key, lo, hi) in float_bounds.items():
        raw = (params.get(name, "") or "").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            return None, f"{name} must be a number"
        if not lo <= value <= hi:
            return None, f"{name} must be between {lo} and {hi}"
        filters[key] = value
    for low_key, high_key in (
        ("min_year", "max_year"),
        ("min_citations", "max_citations"),
        ("min_impact_factor", "max_impact_factor"),
    ):
        if (
            low_key in filters
            and high_key in filters
            and filters[low_key] > filters[high_key]
        ):
            return None, f"{low_key} must not exceed {high_key}"
    return (filters or None), None

#: Largest accepted Connected Papers seed id (Semantic Scholar 40-char SHA
#: or DOI). Same fan-out class as _MAX_DOI_CHARS (cache key + upstream fetch
#: + logs); 500 chars is far past any real seed.
_MAX_CP_PAPER_ID_CHARS = 500

#: Import modes the leaf Zotero reflection supports (hub parity: all /
#: collection / tags on the local-DB reader). Anything else is a 400.
_ZOTERO_IMPORT_MODES = ("all", "collection", "tags")

#: Largest accepted library paper_id on every endpoint that resolves one
#: (enrich, save, save-bulk, import, load). The id is a single path
#: component under MASTER/, so it can never exceed the filesystem's
#: 255-byte NAME_MAX -- anything longer names no real record, and
#: unclamped it crashes the stat/write call (OSError: File name too long)
#: while the 400/404 bodies echo the value back whole.
_MAX_LIBRARY_ID_CHARS = 255

#: Largest accepted raw BibTeX text on library_import. The import arrives
#: form-encoded, so the JSON body-bytes guard never sees it, and a single
#: giant entry parses whole before the _MAX_BULK_ITEMS count cap can
#: engage -- so unbounded text is per-request parse + memory pressure.
#: 1M chars admits the documented 500-entry bulk use (~2k chars/entry)
#: with headroom.
_MAX_IMPORT_TEXT_CHARS = 1_000_000

#: Largest accepted saved-search row count per user. Per-row values are
#: already capped, but the rows file is re-read whole per list call, so an
#: unbounded row count lets one scripted caller bloat every future list
#: call for that user; 500 rows is far past any curated set of searches.
_MAX_SAVED_SEARCHES = 500


def _overlong_doi_response():
    return JsonResponse(
        {"error": f"doi must be at most {_MAX_DOI_CHARS} characters"},
        status=400,
    )


def _json_body(request):
    """Parse the JSON body, refusing oversized payloads before parsing."""
    raw = request.body or b"{}"
    if len(raw) > _MAX_JSON_BODY_BYTES:
        raise ValueError("Request body too large")
    return json.loads(raw)


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
    otherwise ``MASTER/<library_id>`` could escape the library root. It
    must also fit in one component (NAME_MAX 255): anything longer names
    no real record, and unclamped it crashes the stat/write call while the
    error bodies echo the value (and the server path) back whole. The
    refusal message is FIXED -- it never carries the value.
    """
    if not isinstance(library_id, str):
        raise ValueError("unsafe library_id: not a string")
    if len(library_id) > _MAX_LIBRARY_ID_CHARS:
        raise ValueError(
            f"unsafe library_id: longer than {_MAX_LIBRARY_ID_CHARS} characters"
        )
    if not library_id or "/" in library_id or "\\" in library_id or "\x00" in library_id:
        raise ValueError("unsafe library_id: not a single path component")
    if library_id in (".", ".."):
        raise ValueError("unsafe library_id: traversal token")
    return library_id


def _assert_safe_project_name(project: str) -> str:
    """A project filing/filter target is a single path component.

    Same jail class as ``_assert_safe_library_id``: a project name becomes
    ``<library_root>/<project>/``, so a separator, NUL, or traversal token
    would escape the library root. The refusal message is FIXED -- it never
    carries the value (same reflection class as the library_id echoes).
    Reserved store names (MASTER, downloads, ...) are refused too: they are
    real directories under the root but never projects, and the picker
    filter excludes them for the same reason.

    The SDK header picker navigates with ``?project=<owner>/<slug>`` (the
    provider id contract), so a value carrying exactly one ``owner/``
    prefix is accepted by filtering on its last component -- the slug is
    the filing directory, the owner is identity context, not a path.
    Anything else with a separator still fails closed.
    """
    from scitex_scholar.storage._project_reconcile import RESERVED_LIBRARY_DIRS

    if not isinstance(project, str):
        raise ValueError("unsafe project name: not a string")
    if "\\" in project or "\x00" in project:
        raise ValueError("unsafe project name: not a single path component")
    # Accept the SDK picker id form ``owner/slug``: the slug (last
    # component) is the filing directory. Deeper paths stay refused.
    parts = project.split("/")
    if len(parts) == 2 and all(parts):
        project = parts[1]
    elif not project or "/" in project:
        raise ValueError("unsafe project name: not a single path component")
    if project in (".", ".."):
        raise ValueError("unsafe project name: traversal token")
    if project.upper() in {name.upper() for name in RESERVED_LIBRARY_DIRS}:
        raise ValueError("unsafe project name: reserved store name")
    return project


def _checked_project_dir(root: Path, project: str) -> Path:
    """Validate a filing/filter target and return its directory.

    Fail-closed: an unsafe name, a reserved store name, or a missing /
    non-directory / symlinked path raises ValueError BEFORE anything is
    written, so callers can validate up front and never leave a half-saved
    paper behind.
    """
    name = _assert_safe_project_name(project)
    pdir = root / name
    if pdir.is_symlink() or not pdir.is_dir():
        raise ValueError("unknown project: no such project in this library")
    return pdir


def _file_paper_into_project(root: Path, library_id: str, project: str) -> None:
    """File a saved paper under ``<root>/<project>/`` (project sync).

    Creates ``<project>/<library_id> -> ../MASTER/<library_id>`` and stamps
    ``container.projects`` via the existing reconcile verb. The link name is
    the validated library_id (safe, unique); membership and reconcile are
    name-agnostic, so no readable-name machinery is needed here.

    The project directory MUST already exist: callers check it with
    ``_checked_project_dir`` BEFORE the save. A real file occupying the link
    path, or a symlink failure, raises OSError (fail loud, fixed message).
    """
    from scitex_scholar.storage._project_reconcile import add_project_to_master

    pdir = _checked_project_dir(root, project)
    master_id = _assert_safe_library_id(library_id)
    link = pdir / master_id
    for existing in pdir.iterdir():
        if not existing.is_symlink() or existing == link:
            continue
        try:
            if existing.resolve().name == master_id:
                existing.unlink()
        except (OSError, RuntimeError):
            continue
    if link.is_symlink():
        try:
            resolved = link.resolve().name == master_id
        except (OSError, RuntimeError):
            resolved = False
        if resolved:
            add_project_to_master(root, master_id, pdir.name)
            return
        link.unlink()
    elif link.exists():
        raise OSError("cannot file into project: link path is occupied")
    link.symlink_to(f"../MASTER/{master_id}")
    add_project_to_master(root, master_id, pdir.name)


def _load_library_paper(root: Path, paper_id: str):
    """Load one primary metadata.json as a Paper, keyed by paper_id.

    Real library files store {"metadata": {...}} with no "container", so the
    paper_id is set explicitly -- that is what PaperIO needs to write back to
    the same MASTER/<paper_id>/ directory on save.
    """
    from scitex_scholar.core.Paper import Paper

    paper_id = _assert_safe_library_id(paper_id)
    meta_path = root / "MASTER" / paper_id / "metadata.json"
    data = json.loads(meta_path.read_text())
    paper = Paper.from_dict(data)
    paper.container.library_id = paper_id
    return paper


def _save_library_paper(paper, root: Path) -> Path:
    """Persist an enriched Paper to its primary dir.

    The library is the user's local primary files; the view writes them directly
    (PaperIO) and does NOT touch the shared relational library index -- that
    store is keyed by the running user, and rebuilding it here would couple the
    GUI to a store the app may not own. Reading back is done straight from the
    primary files (see library_list), which is the same user-scope guarantee.

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

    Returns {papers: [...], count, total, filtered, query}.
    Reads the user's primary metadata files directly (``collect_rows`` -- "no
    store involved"), scoped to the request's user (see ``_library_root_for``),
    so a mounted hub never exposes one shared service-account library to every
    user. The server-side root stays server-side: the payload carries paper
    rows only, never the filesystem path (it names the service account and
    jail layout on a mounted host). An empty or missing library is an empty
    list, not an error.

    ``filtered`` says whether a filter was APPLIED, and ``total`` how many
    papers the library holds before it. The client needs both to tell "you have
    no papers" from "your filter matched none" -- the two states carry
    different copy and different actions, and without the flag the filtered
    empty state is dead code no user can ever reach.
    """
    root = _library_root_for(request)
    from scitex_scholar.storage import _library_index as idx

    query = (request.GET.get("q") or "").strip()
    if len(query) > _MAX_QUERY_CHARS:
        return JsonResponse(
            {"error": f"q must be at most {_MAX_QUERY_CHARS} characters"},
            status=400,
        )
    project = (request.GET.get("project") or "").strip()
    if project:
        # A filter that escapes the library root fails closed, like the
        # filing path. The message is fixed; the value is never echoed.
        try:
            _assert_safe_project_name(project)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        # The filter names a FILING location: it narrows only when that
        # project exists under this request's library root. A selection
        # that corresponds to nothing here (a hand-typed query, or a
        # mounted host's project id) leaves the request-bound root alone --
        # an explicit project selection never redirects the listing.
        if (root / project).is_symlink() or not (root / project).is_dir():
            project = ""
    try:
        command = _parse_library_query(query)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    def _payload(papers: list, total: int) -> dict:
        # Success body carries server-computed result only: the client
        # already holds the filter text in its own input box, and no
        # JS/template consumer reads a `query` key -- echoing raw caller
        # input back whole is pure reflection surface. A project filter
        # counts as filtering too, so the empty state stays reachable.
        return {
            "papers": papers,
            "count": len(papers),
            "total": total,
            "filtered": bool(query) or bool(project),
        }

    try:
        rows = idx.collect_rows(root)
    except FileNotFoundError:
        return JsonResponse(_payload([], 0))
    except ValueError as e:
        # Duplicate DOIs across primary entries == library corruption; surface it
        # rather than silently listing an inconsistent view.
        logger.error(f"library list: {e}")
        return JsonResponse({"error": "Library index inconsistent. Rebuild or repair the library."}, status=500)

    try:
        from scitex_scholar.storage import _project_reconcile as _pr

        membership, _broken = _pr.build_project_membership(root)
    except OSError:
        membership = {}

    from scitex_scholar.storage import _library_annotations as _ann

    def _row_annotations(paper_id: str) -> dict:
        # Slice 4a: merge the annotations sidecar into each row. A missing
        # or corrupt sidecar degrades to {} (read_annotations never raises),
        # so an un-annotated library lists exactly as before this slice.
        if not paper_id:
            return {}
        try:
            safe_id = _assert_safe_library_id(paper_id)
        except ValueError:
            return {}
        return _ann.read_annotations(root / "MASTER" / safe_id)

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
            # Project-sync (parity slice 3c): which projects file this
            # paper, from the existing symlink-membership verb. Unfiled
            # papers carry [], never null, so the client can filter
            # without a second round-trip.
            "projects": sorted(membership.get(r.get("paper_id") or "", ())),
            "annotations": _row_annotations(r.get("paper_id") or ""),
        }
        for r in rows
    ]
    if project:
        papers = [p for p in papers if project in p["projects"]]
    if query:
        papers = _filter_library_papers(papers, query, command)
    return JsonResponse(_payload(papers, len(rows)))


def _parse_library_query(query: str):
    """Adapt existing query parsers to fields present in Library rows."""
    if not query:
        return None
    import re

    # Plain queries keep their existing whole-query substring behavior.
    operator = r"(?<!\S)(?:--?[\w-]+|(?:year|citations?|impact_factor|if|open_access|oa|type):)"
    if not re.search(operator, query, re.IGNORECASE):
        return None
    unsupported = r"(?<!\S)(?:-ifmin\b|-ifmax\b|--if-min\b|--if-max\b|(?:impact_factor|if|open_access|oa|type):)"
    if re.search(unsupported, query, re.IGNORECASE):
        raise ValueError("Library command filters do not support IF, OA or type")

    from scitex_scholar.pipelines.SearchQueryParser import SearchQueryParser

    shell = SearchQueryParser.from_shell_syntax(query)
    options = {
        "-t", "--title", "-a", "--author", "-j", "--journal",
        "-ymin", "--year-min", "-ymax", "--year-max",
        "-cmin", "--citations-min", "-cmax", "--citations-max",
    }
    if any(word.casefold() in options or word.startswith("--") for word in shell.positive_keywords):
        raise ValueError("Invalid Library command option or value")
    normal = SearchQueryParser(shell.get_keyword_query())
    fields = {**normal.get_filters(), **shell.get_filters()}
    if any(key in fields for key in ("min_impact_factor", "max_impact_factor", "open_access", "document_type")):
        raise ValueError("Library command filters do not support IF, OA or type")
    # Numeric filters use apply_filters' explicit None checks, including zero.
    names = {
        "year_start": "year_from", "year_end": "year_to",
        "min_citations": "min_citations", "max_citations": "max_citations",
    }
    numeric = {target: fields[source] for source, target in names.items() if source in fields}
    text = {key: value for key, value in fields.items() if key.endswith(("_includes", "_excludes"))}
    return {
        "query": normal.get_keyword_query(),
        "negative_keywords": normal.negative_keywords,
        "filters": numeric,
        "operators": text,
    }


def _filter_library_papers(papers: list, query: str, command) -> list:
    """Filter temporary scalar projections and return original public rows."""
    if command is None:
        return [paper for paper in papers if _paper_matches(paper, query)]

    from scitex_scholar.filters import apply_filters

    selected = []
    for paper in papers:
        if command["query"] and not _paper_matches(paper, command["query"]):
            continue
        if any(_paper_matches(paper, word) for word in command["negative_keywords"]):
            continue
        authors = [
            str(author if isinstance(author, str) else author.get("name") or "")
            for author in (paper.get("authors") or [])
            if isinstance(author, (str, dict))
        ]
        projection = {
            "title": str(paper.get("title") or ""),
            "authors": authors,
            "journal": str(paper.get("venue") or ""),
            "year": paper.get("year"),
            "citations": paper.get("citation_count"),
        }
        if apply_filters([projection], command["filters"], command["operators"]):
            selected.append(paper)
    return selected


def _paper_matches(paper: dict, query: str) -> bool:
    """Case-insensitive substring match over the fields the UI shows.

    Authors arrive as names or objects depending on the primary record, so both
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

    Body: {"paper_id": str, "force": bool}. Loads the primary record, runs the
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
    # paper_id is a single path component under MASTER/ (NAME_MAX 255), so a
    # longer value can never name a real record -- fail closed BEFORE any
    # filesystem touch, and without echoing the value (the 400/404 bodies
    # would otherwise carry it back whole).
    if len(paper_id) > _MAX_LIBRARY_ID_CHARS:
        return JsonResponse(
            {"error": f"paper_id must be at most {_MAX_LIBRARY_ID_CHARS} characters"},
            status=400,
        )
    # paper_id is a body-key path sink (MASTER/<paper_id>/metadata.json):
    # fail closed BEFORE any filesystem touch, so a traversal or absolute
    # value can neither probe nor load records outside the user root.
    try:
        paper_id = _assert_safe_library_id(paper_id)
    except ValueError:
        return JsonResponse({"error": "invalid paper_id"}, status=400)
    force = (request.POST.get("force") or "").lower() in ("1", "true", "yes")

    root = _library_root_for(request)
    meta_path = root / "MASTER" / paper_id / "metadata.json"
    if not meta_path.is_file():
        return JsonResponse({"error": "library paper not found"}, status=404)

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
        # The success body carries state + server-computed enrichment only
        # (doi/title/year resolved from the databases), never the
        # caller-supplied paper_id back: the only client (library.js) posts
        # the id from its own row state and reads abstract_chars,
        # citation_count, and title -- nothing reads a paper_id key, so the
        # echo is pure round-trip (same reflection class as the save path
        # leak, the list query echo, and the import paper_ids echo).
        return JsonResponse(
            {
                "ok": True,
                "doi": m.id.doi,
                "title": m.basic.title,
                "year": m.basic.year,
                "abstract_chars": len(m.basic.abstract or ""),
                "citation_count": m.citation_count.total,
            }
        )
    except Exception as e:
        logger.error(f"library enrich failed for {paper_id!r}: {e}", exc_info=True)
        return JsonResponse({"error": "Enrichment failed. Try again later."}, status=500)


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

LIBRARY_EXPORT_FORMATS = ("bibtex", "ris", "endnote", "csv")
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
        "pmid": row.get("pmid"),
        "abstract": row.get("abstract"),
    }


def _paper_obj_to_formatting_dict(paper) -> dict:
    """Map a loaded Paper object to the dict shape papers_to_format expects.

    Same keys as _row_to_formatting_dict (which maps index rows); the two
    stay in sync so single-paper and whole-library exports render
    identically.
    """
    authors = paper.metadata.basic.authors or []
    names = [
        a if isinstance(a, str) else (a.get("name") if isinstance(a, dict) else str(a))
        for a in authors
        if a
    ]
    return {
        "title": paper.metadata.basic.title or "",
        "authors": names,
        "authors_str": " and ".join(names),
        "year": paper.metadata.basic.year,
        "journal": getattr(paper.metadata.publication, "journal", None),
        "doi": paper.metadata.id.doi or "",
        "pmid": getattr(paper.metadata.id, "pmid", None),
        "abstract": paper.metadata.basic.abstract,
    }


@require_GET
def library_citation(request):
    """Format ONE library paper's citation (hub export get_citation parity).

    ?library_id= (required) + ?format= over LIBRARY_EXPORT_FORMATS
    (default bibtex). Returns {"citation": <string>, "format": fmt} for
    copy-paste. Unknown papers are 404; traversal ids are 400 via the
    shared validator. ?format= travels by GET, so no body cap applies.
    """
    fmt = (request.GET.get("format") or "bibtex").strip().lower()
    if fmt not in LIBRARY_EXPORT_FORMATS:
        return JsonResponse(
            {
                "error": "Unsupported export format",
                "supported": list(LIBRARY_EXPORT_FORMATS),
            },
            status=400,
        )
    try:
        safe_id = _assert_safe_library_id(request.GET.get("library_id", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    root = _library_root_for(request)
    if not (root / "MASTER" / safe_id / "metadata.json").is_file():
        return JsonResponse({"error": "Paper not found"}, status=404)
    from scitex_scholar.formatting import papers_to_format, to_csv_row

    try:
        paper = _load_library_paper(root, safe_id)
        formatted = _paper_obj_to_formatting_dict(paper)
        if fmt == "csv":
            import csv as _csv
            import io as _io

            buffer = _io.StringIO()
            fieldnames = [
                "Title",
                "Authors",
                "Journal",
                "Year",
                "DOI",
                "PMID",
                "URL",
                "Abstract",
            ]
            writer = _csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(to_csv_row(formatted))
            citation = buffer.getvalue()
        else:
            citation = papers_to_format([formatted], fmt)
    except Exception as e:
        logger.error(f"library citation ({fmt}) failed: {e}", exc_info=True)
        return JsonResponse({"error": "Citation failed. Try again later."}, status=500)
    return JsonResponse({"citation": citation, "format": fmt})


@require_GET
def library_export(request):
    """Export the user's local library to bibtex / ris / endnote / csv.

    ?format=bibtex|ris|endnote|csv (default bibtex). Streams the serialized
    library as the response body with the right content type. CSV uses the
    hub column set (Title/Authors/Journal/Year/DOI/PMID/URL/Abstract) via
    the package's to_csv_row (old-direct unification slice 7).
    """
    fmt = (request.GET.get("format") or "bibtex").strip().lower()
    if fmt not in LIBRARY_EXPORT_FORMATS:
        # Fixed message: the raw value is untrusted input and must never be
        # echoed back whole (same echo class as the import-format 400).
        # ?format= travels by GET, so no body cap applies.
        return JsonResponse(
            {
                "error": "Unsupported export format",
                "supported": list(LIBRARY_EXPORT_FORMATS),
            },
            status=400,
        )

    root = _library_root_for(request)
    from scitex_scholar.formatting import papers_to_format, to_csv_row
    from scitex_scholar.storage import _library_index as idx

    try:
        rows = idx.collect_rows(root)
    except FileNotFoundError:
        rows = []
    except ValueError as e:
        return JsonResponse({"error": "Library index inconsistent. Rebuild or repair the library."}, status=500)

    try:
        if fmt == "csv":
            import csv as _csv
            import io as _io

            buffer = _io.StringIO()
            fieldnames = [
                "Title",
                "Authors",
                "Journal",
                "Year",
                "DOI",
                "PMID",
                "URL",
                "Abstract",
            ]
            writer = _csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(to_csv_row(_row_to_formatting_dict(row)))
            content = buffer.getvalue()
        else:
            content = papers_to_format([_row_to_formatting_dict(r) for r in rows], fmt)
    except Exception as e:
        logger.error(f"library export ({fmt}) failed: {e}", exc_info=True)
        return JsonResponse({"error": "Export failed. Try again later."}, status=500)

    content_type = {
        "bibtex": "application/x-bibtex",
        "ris": "application/x-research-info-systems",
        "endnote": "application/x-endnote-references",
        "csv": "text/csv",
    }[fmt]
    ext = {"bibtex": "bib", "ris": "ris", "endnote": "enw", "csv": "csv"}[fmt]
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


def _preview_import_entry(paper, root: Path) -> dict:
    """One parsed BibTeX entry for the import preview (no writes).

    The derived library_id is computed exactly as the save path computes
    it, so the ``exists`` flag answers whether confirming would upsert an
    entry that is already in the library. The id itself is NOT echoed
    (same reflection rule as the save-bulk row handles); only display
    fields travel.
    """
    library_id = _assert_safe_library_id(_derived_library_id(paper))
    authors = paper.metadata.basic.authors or []
    return {
        "title": paper.metadata.basic.title or "",
        "authors": [a for a in authors if isinstance(a, str)],
        "year": paper.metadata.basic.year,
        "venue": getattr(paper.metadata.publication, "journal", None),
        "doi": paper.metadata.id.doi or "",
        "exists": (root / "MASTER" / library_id / "metadata.json").is_file(),
    }


@require_POST
def library_import(request):
    """Import BibTeX into the user's local library.

    Body: format=bibtex (default) + bibtex=<bibliography text>. Each entry is
    parsed by the package's BibTeX handler and persisted to the same
    MASTER/<paper_id>/metadata.json path the list/enrich routes read, so imported
    papers are immediately visible and enrichable.

    With preview=1 the entries are parsed and REPORTED (title/authors/year/
    doi + whether each already exists) without writing anything -- hub's
    preview-before-save step, minus the async job machinery. The confirm
    path below is byte-for-byte the pre-slice save flow.
    """
    fmt = (request.POST.get("format") or "bibtex").strip().lower()
    if fmt not in LIBRARY_IMPORT_FORMATS:
        # Fixed message: the raw value is untrusted input and must never be
        # echoed back whole (same echo class as the numeric-param 400s).
        return JsonResponse(
            {
                "error": "Unsupported import format",
                "supported": list(LIBRARY_IMPORT_FORMATS),
            },
            status=400,
        )
    bibtex_text = (request.POST.get("bibtex") or "").strip()
    if not bibtex_text:
        return JsonResponse({"error": "bibtex field required"}, status=400)
    if len(bibtex_text) > _MAX_IMPORT_TEXT_CHARS:
        return JsonResponse(
            {"error": f"bibtex text must be at most {_MAX_IMPORT_TEXT_CHARS} characters"},
            status=413,
        )

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
        if len(papers) > _MAX_BULK_ITEMS:
            return JsonResponse(
                {"error": f"Too many entries: at most {_MAX_BULK_ITEMS} per import"},
                status=400,
            )

        if (request.POST.get("preview") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            # Preview-before-save (old-direct unification slice 5): report
            # the parsed entries with exists flags, write nothing.
            return JsonResponse(
                {
                    "preview": True,
                    "entries": [_preview_import_entry(p, root) for p in papers],
                }
            )

        imported = []
        for paper in papers:
            # Validate the id is a single safe path component BEFORE persisting,
            # so MASTER/<library_id> can never escape the library root.
            library_id = _assert_safe_library_id(_derived_library_id(paper))
            paper.container.library_id = library_id
            _save_library_paper(paper, root)
            imported.append(library_id)

        # The success body reports STATE ONLY: the imported count (the toast
        # reads data.imported, then loadLibrary refreshes authoritative
        # state). The per-paper ids are derived from caller-supplied BibTeX
        # content and are unread in static/ + templates/ -- echoing them is
        # the same reflection class as the save-bulk library_id echo.
        return JsonResponse({"ok": True, "imported": len(imported)})
    except Exception as e:
        logger.error(f"library import failed: {e}", exc_info=True)
        return JsonResponse({"error": "Import failed. Try again later."}, status=500)


def _resolve_zotero_reader(_reader):
    """The local-DB reader behind the Zotero views, with a test seam.

    ``_reader`` is None in production (construct the real
    ZoteroLocalReader, which raises FileNotFoundError when no local
    database exists); a test passes either a prebuilt stand-in instance
    or a zero-arg factory (e.g. a raising stand-in class). The
    collaborator is a PARAMETER, not a monkeypatch (PA-306), exactly as
    ``library_enrich(request, _pipeline=)``.
    """
    if _reader is None:
        from scitex_scholar.integration.zotero import ZoteroLocalReader

        return ZoteroLocalReader()
    if isinstance(_reader, type):
        return _reader()
    return _reader


def _persist_imported_papers(papers, root, request) -> tuple:
    """Persist package Papers into the leaf store; return (imported, skipped).

    Each paper gets a derived, dedup-friendly library_id (same function
    the BibTeX import uses) and the request user's stamp. A paper whose id
    OR DOI already exists is SKIPPED, never overwritten: the stored record
    may carry enrichment the fresh import would clobber. One bad paper
    cannot fail the batch (same per-row class as library_save_bulk).
    """
    from scitex_scholar.storage import _library_index as idx

    try:
        known_dois = {
            str(r.get("doi") or "").strip().lower() for r in idx.collect_rows(root)
        }
    except (FileNotFoundError, ValueError):
        # No library yet, or an inconsistent one the list endpoint already
        # surfaces -- neither may fail an import; id checks still dedupe.
        known_dois = set()
    user = getattr(request, "user", None)
    imported = skipped = 0
    for paper in papers:
        try:
            library_id = _assert_safe_library_id(_derived_library_id(paper))
            doi = str(paper.metadata.id.doi or "").strip().lower()
        except Exception:
            skipped += 1
            continue
        if (root / "MASTER" / library_id / "metadata.json").is_file() or (
            doi and doi in known_dois
        ):
            skipped += 1
            continue
        try:
            paper.container.library_id = library_id
            paper.container.created_by = (
                _safe_username(user) if user is not None else "user"
            )
            _save_library_paper(paper, root)
        except Exception as e:
            logger.warning(f"library ext import: skipping one paper ({e})")
            skipped += 1
            continue
        imported += 1
        if doi:
            known_dois.add(doi)
    return imported, skipped


@require_GET
def zotero_status(request, _reader=None):
    """Whether a local Zotero database is reachable on this host.

    Returns {available: bool} only: the reader's FileNotFoundError text
    names server-side search paths, so it must never reach the client
    (same non-echo class as the library-root payload rule).
    """
    try:
        _resolve_zotero_reader(_reader)
    except FileNotFoundError:
        return JsonResponse({"available": False})
    except Exception as e:
        logger.warning(f"zotero status check failed: {e}")
        return JsonResponse({"available": False})
    return JsonResponse({"available": True})


@require_GET
def zotero_collections(request, _reader=None):
    """List local Zotero collections for the import mode picker."""
    try:
        reader = _resolve_zotero_reader(_reader)
        return JsonResponse({"collections": list(reader.list_collections())})
    except FileNotFoundError:
        return JsonResponse(
            {"error": "Zotero database not available"}, status=404
        )
    except Exception as e:
        logger.warning(f"zotero collections failed: {e}")
        return JsonResponse({"error": "Zotero database not available"}, status=500)


@require_POST
def zotero_import(request, _reader=None):
    """Import papers from the local Zotero database into the leaf library.

    Body (JSON): {mode: all|collection|tags, collection?: str,
    tags?: [str]|"a, b", match_all?: bool}. Reads via ZoteroLocalReader
    and persists through the same MASTER/<id>/metadata.json path the
    list/enrich routes read, so imported papers are immediately visible
    and enrichable. Caps at _MAX_BULK_ITEMS (same class as
    library_import). Bodies over 256k are refused with 413 before parsing.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    mode = (payload.get("mode") or "all")
    if not isinstance(mode, str):
        mode = "all"
    mode = mode.strip().lower()
    if mode not in _ZOTERO_IMPORT_MODES:
        # Fixed message: the raw mode is untrusted input (echo class).
        return JsonResponse(
            {"error": "Unsupported import mode", "supported": list(_ZOTERO_IMPORT_MODES)},
            status=400,
        )
    collection = payload.get("collection") or ""
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(collection, str) or not isinstance(tags, list) or any(
        not isinstance(t, str) for t in tags
    ):
        return JsonResponse({"error": "Invalid collection or tags"}, status=400)
    if len(collection) + sum(len(t) for t in tags) > _MAX_QUERY_CHARS:
        return JsonResponse(
            {"error": "collection/tags filter too long"}, status=400
        )
    if mode == "collection" and not collection.strip():
        return JsonResponse(
            {"error": "collection required for collection mode"}, status=400
        )
    if mode == "tags" and not tags:
        return JsonResponse({"error": "tags required for tags mode"}, status=400)
    match_all = payload.get("match_all", False)
    try:
        reader = _resolve_zotero_reader(_reader)
        if mode == "collection":
            papers = list(reader.read_by_collection(collection.strip()))
        elif mode == "tags":
            papers = list(reader.read_by_tags(tags, match_all=bool(match_all)))
        else:
            papers = list(reader.read_all())
    except FileNotFoundError:
        return JsonResponse(
            {"error": "Zotero database not available"}, status=404
        )
    except Exception as e:
        logger.error(f"zotero import failed: {e}", exc_info=True)
        return JsonResponse({"error": "Import failed. Try again later."}, status=500)
    if len(papers) > _MAX_BULK_ITEMS:
        return JsonResponse(
            {"error": f"Too many entries: at most {_MAX_BULK_ITEMS} per import"},
            status=400,
        )
    root = _library_root_for(request)
    imported, skipped = _persist_imported_papers(papers, root, request)
    return JsonResponse(
        {"ok": True, "imported": imported, "skipped": skipped, "total": len(papers)}
    )


@require_GET
def connected_papers_status(request, _probe=None):
    """Whether the Connected Papers integration is available (hub parity:
    the ``connectedpapers`` package import check).

    ``_probe`` is a test-injection seam (PA-306): Django routes call with
    only ``request``; tests pass True/False directly.
    """
    if _probe is None:
        try:
            import connectedpapers  # noqa: F401
        except ImportError:
            return JsonResponse({"available": False})
        return JsonResponse({"available": True})
    return JsonResponse({"available": bool(_probe)})


@require_POST
def connected_papers_import(request, _importer=None):
    """Import a Connected Papers graph into the leaf library by seed paper.

    Body (JSON): {paper_id: str (S2 40-char SHA or DOI), dry_run?: bool,
    cp_api_key?: str, s2_api_key?: str}. Fetches with output_format
    "papers" and persists through the leaf store, same as zotero_import.
    The seed id is untrusted input: blank is a 400, oversized is a 400,
    both FIXED messages (echo class). Upstream failures are a 500 with a
    fixed message -- CP/network error text is server-side detail.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    paper_id = payload.get("paper_id") or ""
    if not isinstance(paper_id, str):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    paper_id = paper_id.strip()
    if not paper_id:
        return JsonResponse({"error": "A seed paper is required"}, status=400)
    if len(paper_id) > _MAX_CP_PAPER_ID_CHARS:
        return JsonResponse(
            {"error": f"Seed id must be at most {_MAX_CP_PAPER_ID_CHARS} characters"},
            status=400,
        )
    dry_run = bool(payload.get("dry_run", False))
    try:
        importer = _importer
        if importer is None:
            from scitex_scholar.migration import from_connected_papers

            importer = from_connected_papers
        result = importer(
            paper_id,
            cp_api_key=payload.get("cp_api_key") or None,
            s2_api_key=payload.get("s2_api_key") or None,
            output_format="papers",
            dry_run=dry_run,
        )
    except Exception as e:
        logger.error(f"connected papers import failed: {e}", exc_info=True)
        return JsonResponse({"error": "Import failed. Try again later."}, status=500)
    if not result.get("success"):
        return JsonResponse({"error": "Import failed. Try again later."}, status=500)
    stats = result.get("stats", {})
    warnings = result.get("warnings", [])
    if dry_run:
        return JsonResponse(
            {"ok": True, "dry_run": True, "stats": stats, "warnings": warnings}
        )
    papers = list(result.get("papers") or [])
    if len(papers) > _MAX_BULK_ITEMS:
        return JsonResponse(
            {"error": f"Too many entries: at most {_MAX_BULK_ITEMS} per import"},
            status=400,
        )
    root = _library_root_for(request)
    imported, skipped = _persist_imported_papers(papers, root, request)
    return JsonResponse(
        {
            "ok": True,
            "imported": imported,
            "skipped": skipped,
            "total": len(papers),
            "stats": stats,
            "warnings": warnings,
        }
    )


def _paper_from_save_payload(payload):
    """Adapt a library-list row or a nested Paper dict at the HTTP boundary.

    The core Paper schema stays nested; library_list's public row shape is
    flat. Passing that row straight to Paper.from_dict silently drops its
    fields, so both save endpoints translate it here before validation.
    """
    from scitex_scholar.core.Paper import Paper

    if not isinstance(payload, dict):
        raise ValueError("Paper must be a JSON object")
    if "metadata" in payload or "container" in payload:
        return Paper.from_dict(payload)

    authors = payload.get("authors")
    if isinstance(authors, list):
        authors = [
            author.get("name") if isinstance(author, dict) else author
            for author in authors
        ]
    return Paper.from_dict(
        {
            "metadata": {
                "id": {"doi": payload.get("doi")},
                "basic": {
                    "title": payload.get("title"),
                    "year": payload.get("year"),
                    "abstract": payload.get("abstract"),
                    "authors": authors,
                },
                "publication": {"journal": payload.get("venue")},
                "citation_count": {"total": payload.get("citation_count")},
            },
            "container": {"library_id": payload.get("paper_id")},
        }
    )


@require_POST
def library_save(request):
    """Save ONE paper to the user's local library (explicit user action).

    Body: the paper object (same shape library_list returns per row, or a
    ``Paper`` dict). The save runs through the file-based primary store
    (PaperIO) under the request's user-scoped root — no shared store, no
    database. ``container.created_by`` is stamped with the request user.
    A missing library_id is derived (DOI/title hash, dedup-friendly).
    Bodies over 256k are refused with 413 before parsing.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    try:
        paper = _paper_from_save_payload(payload)
    except Exception as e:
        return JsonResponse({"error": f"Invalid paper: {e}"}, status=400)
    user = getattr(request, "user", None)
    paper.container.created_by = _safe_username(user) if user is not None else "user"
    if not paper.container.library_id:
        paper.container.library_id = _derived_library_id(paper)
    root = _library_root_for(request)
    # Project sync (parity slice 3c): an optional top-level "project" files
    # the paper under <root>/<project>/ (hub old-direct files saves into the
    # current project tree). Validated BEFORE the save so a refused project
    # never leaves a half-saved paper behind. Absent stays user-scoped.
    project = payload.get("project", None)
    if project is not None:
        if not isinstance(project, str):
            return JsonResponse(
                {"error": "unsafe project name: not a string"}, status=400
            )
        try:
            _checked_project_dir(root, project)
            _file_after_save = True
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
    else:
        _file_after_save = False
    try:
        _save_library_paper(paper, root)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except OSError as e:
        logger.error(f"library save failed: {e}", exc_info=True)
        return JsonResponse({"error": "Save failed. Try again later."}, status=500)
    if _file_after_save:
        # The paper is saved; the filing was pre-validated above, so only a
        # filesystem failure can still occur -- fail loud, fixed message.
        try:
            _file_paper_into_project(root, paper.container.library_id, project)
        except OSError as e:
            logger.error(f"library file-into-project failed: {e}", exc_info=True)
            return JsonResponse(
                {"error": "Saved, but filing into the project failed."}, status=500
            )
    # The body reports STATE + the validated library_id handle only, never
    # the server filesystem path: str(path) names the service account + jail
    # layout (same disclosure class as the library_root list payload).
    return JsonResponse(
        {"saved": True, "library_id": paper.container.library_id, "project": project}
    )


@require_POST
def library_save_bulk(request):
    """Save MANY papers in one call; per-paper results so one bad row cannot
    fail the batch. Body: ``{"papers": [...]}``. Same store, scoping, and
    stamping rules as library_save. Bodies over 256k are refused with
    413 before parsing; batches over 500 items are refused with 400
    before any write (one file write per item would otherwise amplify
    a single request into hundreds of writes). Per-row failures carry
    the row index and a fixed error only -- never the caller-supplied
    library_id back."""
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": 'Body must be {"papers": [...]}'}, status=400)
    papers = payload.get("papers")
    if not isinstance(papers, list):
        return JsonResponse({"error": 'Body must be {"papers": [...]}'}, status=400)
    if len(papers) > _MAX_BULK_ITEMS:
        return JsonResponse(
            {"error": f"papers must contain at most {_MAX_BULK_ITEMS} items"},
            status=400,
        )
    user = getattr(request, "user", None)
    created_by = _safe_username(user) if user is not None else "user"
    root = _library_root_for(request)
    # Project sync (parity slice 3c): an optional top-level "project" files
    # every row under <root>/<project>/ (hub old-direct files saves into the
    # current project tree). Validated BEFORE any write so a refused project
    # fails the whole batch with nothing saved.
    project = payload.get("project", None)
    if project is not None:
        if not isinstance(project, str):
            return JsonResponse(
                {"error": "unsafe project name: not a string"}, status=400
            )
        try:
            _checked_project_dir(root, project)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
    saved, failed = [], []
    for i, item in enumerate(papers):
        try:
            paper = _paper_from_save_payload(item)
        except Exception as e:
            failed.append({"index": i, "error": f"Invalid paper: {e}"})
            continue
        paper.container.created_by = created_by
        if not paper.container.library_id:
            paper.container.library_id = _derived_library_id(paper)
        try:
            _save_library_paper(paper, root)
        except (ValueError, OSError) as e:
            # The failure object identifies the row by index only. The
            # caller-supplied library_id is NEVER reflected: echoing it back
            # whole is the same reflection class as the enrich 400/404
            # paper_id echoes, and the bulk 200 status would otherwise
            # round-trip an arbitrary value verbatim. The error text is the
            # fixed validator message (see _assert_safe_library_id).
            failed.append({"index": i, "error": str(e)})
            continue
        if project is not None:
            try:
                _file_paper_into_project(root, paper.container.library_id, project)
            except OSError as e:
                logger.error(f"library file-into-project failed: {e}", exc_info=True)
                failed.append(
                    {"index": i, "error": "Saved, but filing into the project failed."}
                )
                continue
        # Saved entries carry the validated library_id handle only, never
        # the server filesystem path (same disclosure class as above).
        saved.append({"library_id": paper.container.library_id})
    return JsonResponse({"saved": saved, "failed": failed})


@require_POST
def library_annotate(request):
    """Update one paper's user annotations (reading status, importance, tags, notes).

    Body: {"library_id": ..., "reading_status"?, "importance"?, "tags"?, "notes"?}.
    Partial updates merge into the annotations sidecar
    (``MASTER/<library_id>/annotations.json``) -- never into metadata.json,
    so enrichment rewrites can never clobber user data. Unknown fields are
    refused (400); an unknown paper is 404; a traversal library_id is 400
    via the shared id validator. Bodies over 256k are refused with 413
    before parsing, same as the other library writes.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Body must be an object"}, status=400)
    try:
        safe_id = _assert_safe_library_id(payload.get("library_id", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    root = _library_root_for(request)
    paper_dir = root / "MASTER" / safe_id
    if not (paper_dir / "metadata.json").is_file():
        return JsonResponse({"error": "Paper not found"}, status=404)
    from scitex_scholar.storage import _library_annotations as _ann

    fields = {
        key: value for key, value in payload.items() if key != "library_id"
    }
    clean, error = _ann.validate_annotations(fields)
    if error is not None or clean is None:
        return JsonResponse({"error": error or "Invalid annotations"}, status=400)
    try:
        stored = _ann.write_annotations(paper_dir, clean)
    except OSError as e:
        logger.error(f"library annotate failed: {e}", exc_info=True)
        return JsonResponse({"error": "Annotate failed. Try again later."}, status=500)
    return JsonResponse(
        {"annotated": True, "library_id": safe_id, "annotations": stored}
    )


@require_POST
def library_remove(request):
    """Remove ONE paper from the user's local library (explicit action).

    Deletes the ``MASTER/<library_id>/`` tree (metadata, sidecars, and any
    downloaded PDFs/texts) plus every project filing symlink that points
    at it. Unknown papers are 404; traversal ids are 400 via the shared
    validator. Bodies over 256k are refused with 413 before parsing, same
    as the other library writes. The success body carries state only.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Body must be an object"}, status=400)
    try:
        safe_id = _assert_safe_library_id(payload.get("library_id", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    root = _library_root_for(request)
    paper_dir = root / "MASTER" / safe_id
    if not (paper_dir / "metadata.json").is_file():
        return JsonResponse({"error": "Paper not found"}, status=404)
    try:
        from scitex_scholar.storage import _project_reconcile as _pr

        try:
            membership, _broken = _pr.build_project_membership(root)
        except OSError:
            membership = {}
        for project in membership.get(safe_id, ()):
            try:
                safe_project = _assert_safe_project_name(project)
            except ValueError:
                continue
            link = root / safe_project / safe_id
            try:
                if link.is_symlink():
                    link.unlink()
            except OSError as e:
                logger.error(f"library remove unlink failed: {e}", exc_info=True)
                return JsonResponse(
                    {"error": "Remove failed. Try again later."}, status=500
                )
        import shutil as _shutil

        _shutil.rmtree(paper_dir)
    except OSError as e:
        logger.error(f"library remove failed: {e}", exc_info=True)
        return JsonResponse({"error": "Remove failed. Try again later."}, status=500)
    return JsonResponse({"removed": True})


#: Largest accepted download batch (hub parity: one network fetch per item
#: through the OA strategy's own 60s timeout; an unbounded list parks the
#: worker on network IO per request).
_MAX_DOWNLOAD_IDS = 10


@require_POST
def library_download_pdfs(request, _fetch=None):
    """Download open-access PDFs for library papers (explicit action).

    Body: {"library_ids": [...], at most 10}. Each id resolves under the
    request's user-scoped MASTER/ (a traversal id fails the whole batch
    with 400 via the shared validator); papers without an OA URL and
    unknown papers land in per-index ``failed`` rows, never raised.
    Bodies over 256k are refused with 413 before parsing.

    ``_fetch`` is a test-injection seam (PA-306): an async callable
    ``(oa_url, output_path, metadata=None) -> Path | None``. Production
    uses the package's plain-HTTP OA strategy (NOT the browser-bound
    downloader class, which needs a Playwright context no view owns).
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Body must be an object"}, status=400)
    library_ids = payload.get("library_ids")
    if not isinstance(library_ids, list) or not library_ids:
        return JsonResponse({"error": "library_ids must be a non-empty list"}, status=400)
    if len(library_ids) > _MAX_DOWNLOAD_IDS:
        return JsonResponse(
            {"error": f"library_ids must contain at most {_MAX_DOWNLOAD_IDS} items"},
            status=400,
        )
    safe_ids = []
    for raw_id in library_ids:
        try:
            safe_ids.append(_assert_safe_library_id(raw_id))
        except ValueError as e:
            # Fixed validator message only; the caller-supplied id is never
            # echoed (same reflection class as the save-bulk row handles).
            return JsonResponse({"error": str(e)}, status=400)
    root = _library_root_for(request)
    if _fetch is None:
        from scitex_scholar.pdf_download.strategies.open_access_download import (
            try_download_open_access_async as _fetch,
        )
    from scitex_scholar.storage.PaperIO import PaperIO

    downloaded, failed = [], []
    for i, safe_id in enumerate(safe_ids):
        paper_dir = root / "MASTER" / safe_id
        if not (paper_dir / "metadata.json").is_file():
            failed.append({"index": i, "error": "Paper not found"})
            continue
        try:
            paper = _load_library_paper(root, safe_id)
        except Exception as e:
            logger.error(f"library download-pdfs load failed: {e}", exc_info=True)
            failed.append({"index": i, "error": "Load failed. Try again later."})
            continue
        oa_url = (paper.metadata.access.oa_url or "").strip()
        if not oa_url:
            failed.append({"index": i, "error": "No open-access PDF available"})
            continue
        try:
            fetched = asyncio.run(
                _fetch(oa_url, paper_dir / "download-tmp.pdf", metadata=None)
            )
            if not fetched:
                failed.append({"index": i, "error": "Download failed. Try again later."})
                continue
            io = PaperIO(paper, base_dir=root / "MASTER")
            io.save_pdf(Path(fetched))
            _save_library_paper(paper, root)
            downloaded.append({"library_id": safe_id})
        except Exception as e:
            logger.error(f"library download-pdfs failed: {e}", exc_info=True)
            failed.append({"index": i, "error": "Download failed. Try again later."})
        finally:
            try:
                (paper_dir / "download-tmp.pdf").unlink(missing_ok=True)
            except OSError:
                pass
    return JsonResponse({"downloaded": downloaded, "failed": failed})


def _saved_searches_path(root: Path) -> Path:
    """Single JSON file holding this user's saved searches."""
    return root / "SAVED_SEARCHES" / "saved_searches.json"


def _load_saved_searches(root: Path) -> list:
    path = _saved_searches_path(root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _write_saved_searches(root: Path, rows: list) -> None:
    path = _saved_searches_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows))


@require_POST
def searches_save(request):
    """Save a named search query for this user (explicit action).

    Body: {"name": ..., "query": ..., "params": {...}}. Stored file-based
    under the request's user-scoped root — no shared store, no database.
    Bodies over 256k are refused with 413 before parsing. At most 500 rows
    are stored per user: the rows file is read whole per list call.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    # Bound both: the rows file is read whole per request, so an unbounded
    # value bloats every future list call for that user (and the file).
    # 2k chars each is far past any real saved-search name or query.
    name = (payload.get("name") or "").strip()
    query = (payload.get("query") or "").strip()
    if not name or not query:
        return JsonResponse({"error": "name and query are required"}, status=400)
    if len(name) > _MAX_QUERY_CHARS or len(query) > _MAX_QUERY_CHARS:
        return JsonResponse(
            {"error": f"name and query must each be at most {_MAX_QUERY_CHARS} characters"},
            status=400,
        )
    params = payload.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return JsonResponse({"error": "params must be an object"}, status=400)
    # Bound the serialized params too: no client sends params today (the UI
    # posts name + query only), so an 8k serialized mapping is already far
    # past any legitimate use -- and the rows file is re-read whole per list.
    if len(json.dumps(params)) > 8000:
        return JsonResponse(
            {"error": "params must serialize to at most 8000 characters"},
            status=400,
        )
    user = getattr(request, "user", None)
    root = _library_root_for(request)
    rows = _load_saved_searches(root)
    if len(rows) >= _MAX_SAVED_SEARCHES:
        return JsonResponse(
            {"error": f"at most {_MAX_SAVED_SEARCHES} saved searches per user"},
            status=400,
        )
    import datetime as _dt
    import uuid as _uuid

    row = {
        "id": _uuid.uuid4().hex,
        "name": name,
        "query": query,
        "params": params,
        "created_by": _safe_username(user) if user is not None else "user",
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    rows.append(row)
    try:
        _write_saved_searches(root, rows)
    except OSError as e:
        logger.error(f"searches save failed: {e}", exc_info=True)
        return JsonResponse({"error": "Save failed. Try again later."}, status=500)
    # The success body carries the server-issued id only (the delete
    # handle). The caller-supplied name is NEVER reflected: echoing it back
    # whole is the same reflection class as the delete-id echo below and
    # the save-bulk failed[].library_id echo (slice 23) -- a 200 body
    # round-tripping untrusted input verbatim. No client reads the key.
    return JsonResponse({"saved": True, "id": row["id"]})


@require_GET
def searches_list(request):
    """List this user's saved searches (user-scoped root only)."""
    root = _library_root_for(request)
    return JsonResponse({"searches": _load_saved_searches(root)})


@require_POST
def searches_delete(request):
    """Delete one saved search by id; 404 when unknown. Bodies over 256k are
    refused with 413 before parsing. The success body carries state only:
    the caller-supplied id is NEVER reflected (same reflection class as
    the save-bulk failed[].library_id echo, slice 23)."""
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    search_id = payload.get("id")
    if not search_id:
        return JsonResponse({"error": "id is required"}, status=400)
    root = _library_root_for(request)
    rows = _load_saved_searches(root)
    kept = [r for r in rows if r.get("id") != search_id]
    if len(kept) == len(rows):
        return JsonResponse({"error": "Unknown id"}, status=404)
    try:
        _write_saved_searches(root, kept)
    except OSError as e:
        logger.error(f"searches delete failed: {e}", exc_info=True)
        return JsonResponse({"error": "Delete failed. Try again later."}, status=500)
    return JsonResponse({"deleted": True})


#: Largest serialized `sources` selection stored per user (old-direct U3).
#: Same class as the saved-search params bound: the prefs file is re-read
#: whole per GET, so an unbounded value bloats every future read; 8k chars
#: is far past any legitimate selection (~80 chars for all known sources).
_MAX_SOURCE_PREFS_CHARS = 8000


def _source_preferences_path(root: Path) -> Path:
    """Single JSON file holding this user's source selection."""
    return root / "source-preferences.json"


def _load_source_preferences(root: Path):
    """This user's stored sources, or {} when never saved or unreadable."""
    try:
        return json.loads(_source_preferences_path(root).read_text()).get("sources", {})
    except (OSError, ValueError, AttributeError):
        return {}


@require_http_methods(["GET", "POST"])
def preferences_sources(request):
    """Source-selection persistence (old-direct U3 unification).

    KEEP: hub `save_source_preferences` semantics -- a visitor gets a
    session note (their client owns localStorage) while a file-user gets
    persistence; invalid JSON fails closed (400) with hub's
    {status: error} shape. CHANGE: persistence is a `source-preferences.json`
    under the request's user-scoped root instead of the `UserPreference`
    model (leaf stays off hub DB). GET reads back the stored selection
    ({} default) so both paths round-trip; `?sources=` echo is untouched
    (the search view owns it).
    """
    user = getattr(request, "user", None)
    file_user = bool(getattr(user, "is_authenticated", False))
    root = _library_root_for(request)
    if request.method == "GET":
        sources = _load_source_preferences(root) if file_user else {}
        return JsonResponse({"status": "success", "sources": sources})
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"status": "error", "message": str(e)}, status=413)
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)
    sources = payload.get("sources", {})
    if len(json.dumps(sources)) > _MAX_SOURCE_PREFS_CHARS:
        return JsonResponse(
            {"status": "error", "message": "sources must serialize to at most 8000 characters"},
            status=400,
        )
    if not file_user:
        return JsonResponse(
            {
                "status": "success",
                "message": "Source preferences noted (login to save permanently)",
                "saved_to": "session",
            }
        )
    try:
        path = _source_preferences_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sources": sources}))
    except OSError as e:
        logger.error(f"source preferences save failed: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": "Save failed. Try again later."}, status=500)
    return JsonResponse(
        {
            "status": "success",
            "message": "Source preferences saved to user library",
            "saved_to": "user-root",
        }
    )


# Old-direct parity slice 1 (operator mandate 2026-10-17): hub scholar_app
# keeps SavedGraph rows (name + rebuild recipe); the leaf keeps the same
# shape file-based under the user-scoped root, mirroring saved searches.
# Reload needs no endpoint: GET api/graph/network?doi=<seed_doi> rebuilds.
# Graphs are CUI-owned package data (operator 2026-10-24): the file path
# helper lives in _saved_graph_store._file_path; this module only adapts.
_MAX_SAVED_GRAPHS = 500
_MAX_GRAPH_NAME_CHARS = 200


def _load_saved_graphs(root: Path, _opener=None) -> list:
    # Thin adapter: the CUI owns file + store logic (graphs as package
    # data, operator 2026-10-24); the view only resolves the user root.
    from scitex_scholar.citation_graph._saved_graph_store import list_graphs

    return list_graphs(root, _opener=_opener)


@require_POST
def graphs_save(request, _opener=None):
    """Save a named graph rebuild recipe for this user (explicit action).

    Body: {"name": ..., "seed_doi": ...}. Graphs are package data: the CUI
    keeps the per-user file authoritative and mirrors best-effort into the
    shared store. Bodies over 256k are refused with 413 before parsing. At
    most 500 rows per user. Names cap at 200 (hub SavedGraph.name); seed
    DOIs reuse the 500-char leaf DOI bound. A nameless or seedless row
    cannot rebuild: 400.
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    name = (payload.get("name") or "").strip()
    seed_doi = (payload.get("seed_doi") or "").strip()
    if not name or not seed_doi:
        return JsonResponse({"error": "name and seed_doi are required"}, status=400)
    if len(name) > _MAX_GRAPH_NAME_CHARS:
        return JsonResponse(
            {"error": f"name must be at most {_MAX_GRAPH_NAME_CHARS} characters"},
            status=400,
        )
    if len(seed_doi) > _MAX_DOI_CHARS:
        return JsonResponse(
            {"error": f"seed_doi must be at most {_MAX_DOI_CHARS} characters"},
            status=400,
        )
    user = getattr(request, "user", None)
    root = _library_root_for(request)
    rows = _load_saved_graphs(root)
    if len(rows) >= _MAX_SAVED_GRAPHS:
        return JsonResponse(
            {"error": f"at most {_MAX_SAVED_GRAPHS} saved graphs per user"},
            status=400,
        )
    from scitex_scholar.citation_graph._saved_graph_store import save_graph

    try:
        row = save_graph(
            root,
            name,
            seed_doi,
            _safe_username(user) if user is not None else "user",
            _opener=_opener,
        )
    except OSError as e:
        logger.error(f"graphs save failed: {e}", exc_info=True)
        return JsonResponse({"error": "Save failed. Try again later."}, status=500)
    # Success body carries the server-issued id only (the delete handle);
    # caller input is never reflected (same reflection class as searches).
    return JsonResponse({"saved": True, "id": row["id"]})


@require_GET
def graphs_list(request, _opener=None):
    """List this user's saved graphs (user-scoped root only)."""
    root = _library_root_for(request)
    return JsonResponse({"graphs": _load_saved_graphs(root, _opener=_opener)})


@require_POST
def graphs_delete(request, _opener=None):
    """Delete one saved graph by id; 404 when unknown. Bodies over 256k are
    refused with 413 before parsing. The success body carries state only."""
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    graph_id = payload.get("id")
    if not graph_id:
        return JsonResponse({"error": "id is required"}, status=400)
    root = _library_root_for(request)
    from scitex_scholar.citation_graph._saved_graph_store import delete_graph

    try:
        known = delete_graph(root, graph_id, _opener=_opener)
    except OSError as e:
        logger.error(f"graphs delete failed: {e}", exc_info=True)
        return JsonResponse({"error": "Delete failed. Try again later."}, status=500)
    if not known:
        return JsonResponse({"error": "Unknown id"}, status=404)
    return JsonResponse({"deleted": True})


@require_POST
def graphs_rename(request, _opener=None):
    """Rename one saved graph; 404 when unknown (hub api_rename_graph parity).

    Body: {"id": ..., "name": ...}. Names cap at 200 chars like graphs_save.
    Unlike hub (409 on a name clash), duplicate names are allowed -- the
    leaf save path never enforced uniqueness either, so rename stays
    consistent with save rather than stricter than it. Bodies over 256k
    are refused with 413 before parsing. The success body carries the
    stored id + name (server-issued state, not caller input verbatim --
    the name passed validation first).
    """
    try:
        payload = _json_body(request)
    except ValueError as e:
        if "too large" in str(e):
            return JsonResponse({"error": str(e)}, status=413)
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except TypeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Body must be an object"}, status=400)
    graph_id = payload.get("id")
    if not graph_id:
        return JsonResponse({"error": "id is required"}, status=400)
    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    if len(name) > _MAX_GRAPH_NAME_CHARS:
        return JsonResponse(
            {"error": f"name must be at most {_MAX_GRAPH_NAME_CHARS} characters"},
            status=400,
        )
    root = _library_root_for(request)
    from scitex_scholar.citation_graph._saved_graph_store import rename_graph

    try:
        known = rename_graph(root, graph_id, name, _opener=_opener)
    except OSError as e:
        logger.error(f"graphs rename failed: {e}", exc_info=True)
        return JsonResponse({"error": "Rename failed. Try again later."}, status=500)
    if not known:
        return JsonResponse({"error": "Unknown id"}, status=404)
    return JsonResponse({"renamed": True, "id": graph_id, "name": name})


# EOF
