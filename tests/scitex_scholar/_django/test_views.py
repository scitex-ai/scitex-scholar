#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parity tests for the Django port of the Scholar GUI.

Ports the intent of the Flask-era behaviour (no dedicated Flask test file
existed under tests/scitex_scholar/gui/ beyond a smoke-import mirror, so
this is new coverage written directly against the ported views):

  GET /               -> 200, title + favicon link present
  GET /api/health      -> JSON {"status": "ok", "version", "api_available",
                                "api_url"}
  GET /api/graph/network   -> 400 without ?doi=, 503 with no API configured
  GET /api/graph/related   -> 503 with no API configured
  GET /api/graph/paper     -> 503 with no API configured
  GET /api/graph/health    -> 503 with no API configured

Uses Django's `RequestFactory` directly against the view functions
(bypasses URL routing, same approach as scitex-writer's precedent at
scitex_writer/tests/_django/test_views.py) with a TEST-ONLY settings
bootstrap via conftest.py (bare `django.setup()`, no pytest-django dep).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from django.test import RequestFactory, override_settings

from scitex_scholar._django import views


def test_index_returns_200():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    # Act
    resp = views.index(request)
    # Assert
    assert resp.status_code == 200


def test_index_body_contains_title():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    resp = views.index(request)
    # Act
    body = resp.content.decode()
    # Assert
    assert "<title>SciTeX Scholar</title>" in body


def test_index_body_leaks_no_django_template_comment_markers():
    """No `{#` / `#}` reaches the browser.

    REGRESSION. Django strips `{# ... #}` ONLY when it sits on ONE LINE. A
    multi-line one is emitted verbatim, and this template had a six-line
    explanatory `{# ... #}` above the stx-mount marker -- so a paragraph of
    internal commentary rendered as visible text across the top of the UI.

    The operator found it by looking at the running page. No test caught it,
    because the guards here assert that the RIGHT things are present (the
    marker, the tokens, the title) and nothing asserted the absence of
    WRONG things. Presence-only suites are blind to leakage by construction.
    """
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    # Act
    body = views.index(request).content.decode()
    # Assert
    assert "{#" not in body and "#}" not in body


def test_index_body_leaks_no_unrendered_template_tags():
    """POSITIVE CONTROL for the test above.

    `{#` absence alone would also be satisfied by a template that failed to
    render at all, or by one whose comment syntax someone changed to `{%
    comment %}` while leaving other tags unrendered. Pin that the OTHER
    delimiter never survives either, so the pair fails on any raw template
    syntax reaching the page rather than on one spelling of it.
    """
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    # Act
    body = views.index(request).content.decode()
    # Assert
    assert "{% comment %}" not in body


def test_index_body_contains_shared_branding_favicon():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    resp = views.index(request)
    # Act
    body = resp.content.decode()
    # Assert
    assert '<link rel="icon" href="/static/scitex_ui/img/scitex-favicon.svg"' in body


def test_index_does_not_shadow_shared_favicon_with_inline_icon():
    """Regression guard: a locally hand-rolled icon SHADOWS the shared mark.

    scitex-ui's partial honours a `favicon_href` context var, so
    reintroducing a `data:` URI here would silently win and drift scholar's
    tab away from the rest of the fleet -- the exact bug this replaced.
    """
    # Arrange
    rf = RequestFactory()
    request = rf.get("/")
    resp = views.index(request)
    # Act
    body = resp.content.decode()
    # Assert
    assert 'rel="icon" href="data:' not in body


def test_health_returns_200():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/health")
    # Act
    resp = views.health(request)
    # Assert
    assert resp.status_code == 200


def test_health_response_shape():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/health")
    resp = views.health(request)
    # Act
    data = json.loads(resp.content)
    # Assert
    # EXACT set, not a subset, on purpose: this is the response CONTRACT, so an
    # accidentally-added field fails here rather than reaching callers. It did
    # its job on 2026-08-23 -- adding "version" broke this test before it broke
    # anyone else, which is the whole point of asserting equality.
    assert set(data.keys()) == {"status", "version", "api_available", "api_url"}


def test_graph_network_requires_doi_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/network")
    # Act
    resp = views.graph_network(request)
    # Assert
    assert resp.status_code == 400


@override_settings(CROSSREF_API_URL=None)
def test_graph_network_returns_503_with_no_api_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/network?doi=10.1038/s41586-020-2008-3")
    # Act
    resp = views.graph_network(request)
    # Assert
    assert resp.status_code == 503


def test_graph_related_requires_doi_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/related")
    # Act
    resp = views.graph_related(request)
    # Assert
    assert resp.status_code == 400


@override_settings(CROSSREF_API_URL=None)
def test_graph_related_returns_503_with_no_api_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/related?doi=10.1038/s41586-020-2008-3")
    # Act
    resp = views.graph_related(request)
    # Assert
    assert resp.status_code == 503


def test_graph_paper_requires_doi_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/paper")
    # Act
    resp = views.graph_paper(request)
    # Assert
    assert resp.status_code == 400


@override_settings(CROSSREF_API_URL=None)
def test_graph_paper_returns_503_with_no_api_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/paper?doi=10.1038/s41586-020-2008-3")
    # Act
    resp = views.graph_paper(request)
    # Assert
    assert resp.status_code == 503


@override_settings(CROSSREF_API_URL=None)
def test_graph_health_returns_503_with_no_api_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/health")
    # Act
    resp = views.graph_health(request)
    # Assert
    assert resp.status_code == 503


def test_search_requires_q_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/search")
    # Act
    resp = views.search(request)
    # Assert
    assert resp.status_code == 400


def test_search_rejects_blank_q_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/search?q=%20%20")
    # Act
    resp = views.search(request)
    # Assert
    assert resp.status_code == 400


def test_search_rejects_non_integer_max_results():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/search?q=hippocampus&max_results=many")
    # Act
    resp = views.search(request)
    # Assert
    assert resp.status_code == 400


def test_search_rejects_unknown_mode():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/search?q=hippocampus&mode=telepathy")
    # Act
    resp = views.search(request)
    # Assert
    assert resp.status_code == 400


def test_search_serves_cached_result_without_calling_engine():
    # Arrange -- prime the cache so the engine is never constructed
    key = views._make_cache_key("search", "hippocampus", mode="parallel", max_results=20)
    views._cache_set(key, {"results": [{"title": "Cached paper"}], "metadata": {}})
    request = RequestFactory().get("/api/search?q=hippocampus")
    # Act
    resp = views.search(request)
    # Assert
    assert json.loads(resp.content)["results"][0]["title"] == "Cached paper"


def test_search_marks_cached_results_as_cached():
    # Arrange
    key = views._make_cache_key("search", "sharp wave", mode="parallel", max_results=20)
    views._cache_set(key, {"results": [], "metadata": {}})
    request = RequestFactory().get("/api/search?q=sharp%20wave")
    # Act
    resp = views.search(request)
    # Assert
    assert json.loads(resp.content)["metadata"]["cached"] is True


# ---------------------------------------------------------------------------
# stx-mount marker (scitex-app >= 0.7.0 mount-prefix contract)
#
# The SDK injects this marker only for shells served through
# `scitex_editor_page`. Scholar renders its own Django template, so nothing
# would inject it here -- these tests are the guard that scholar keeps
# supplying it itself. Without the marker the client falls back to "/", which
# is correct standalone and WRONG under any mount prefix, and it fails
# silently: the page renders, and only the API calls 404.
# ---------------------------------------------------------------------------

MOUNT_MARKER = re.compile(r'<meta name="stx-mount" content="([^"]*)"')


def _marker_for(path: str):
    """Render index at `path` and return the stx-mount value the browser sees."""
    response = views.index(RequestFactory().get(path))
    found = MOUNT_MARKER.search(response.content.decode())
    return found.group(1) if found else None


def test_index_emits_stx_mount_marker():
    """The marker must be present -- its absence is a silent prefix failure."""
    # Arrange
    path = "/"

    # Act
    marker = _marker_for(path)

    # Assert
    assert marker is not None


def test_stx_mount_is_empty_when_served_at_root():
    """Standalone root is "" -- NOT "/".

    This test previously asserted "/" and PASSED after the migration, because
    the template carried `|default:'/'` and Django's default filter fires on
    falsy. It was reporting the old value while the SDK returned the new one.
    """
    # Arrange
    path = "/"

    # Act
    marker = _marker_for(path)

    # Assert
    assert marker == ""


def test_stx_mount_reports_the_prefix_it_is_served_under():
    """Embedded: the marker is the real mount, not a guess or a default."""
    # Arrange
    path = "/apps/u/scholar/"

    # Act
    marker = _marker_for(path)

    # Assert
    assert marker == "/apps/u/scholar"


def test_stx_mount_never_ends_in_a_slash():
    """Inverted from the old contract, and the inversion is the point.

    The slash now lives on the ENDPOINT. A base ending in "/" plus an endpoint
    starting with "/" yields "//api/x", which a browser reads as
    protocol-relative and sends OFF-ORIGIN.
    """
    # Arrange
    path = "/apps/u/scholar/"

    # Act
    marker = _marker_for(path)

    # Assert
    assert not marker.endswith("/")


def test_stx_mount_strips_a_trailing_slash_without_losing_the_path():
    """Normalising must not lose the prefix -- that is the failure it prevents."""
    # Arrange
    path = "/apps/u/scholar/"

    # Act
    marker = _marker_for(path)

    # Assert
    assert marker == "/apps/u/scholar"


# ---------------------------------------------------------------------------
# Design-token dependency on scitex-ui (shell/theme.css)
#
# scholar DELETED seven token declarations (--accent, --text-primary,
# --text-secondary, --text-muted, --text-inverse, --border-default,
# --status-error) and now consumes scitex-ui's. That makes them an EXTERNAL
# dependency of scholar's stylesheet, and the failure mode is silent: an
# undefined CSS custom property resolves to nothing rather than erroring, so
# a missing token produces an unstyled page and a green test suite.
#
# Shape borrowed from scitex-ui via hub -- assert every REFERENCED property
# resolves to a declaration. Critically it asserts on the NO-FALLBACK subset
# only: `var(--x, fallback)` is a deliberate override hook, and flagging those
# makes the guard noisy enough to be switched off.
# ---------------------------------------------------------------------------

CSS_DIR = Path(views.__file__).parent / "static" / "scholar" / "css"

SHADOWED_TOKENS = [
    "--accent",
    "--text-primary",
    "--text-secondary",
    "--text-muted",
    "--text-inverse",
    "--border-default",
    "--status-error",
]


TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "scholar.html"
)


CSS_ENTRY = CSS_DIR / "scholar.css"

_IMPORT_RE = re.compile(r"""@import\s+url\(\s*['"]?([^'")]+)['"]?\s*\)""")


def _resolve_css(entry: Path, _seen: set | None = None) -> str:
    """Read `entry` and every stylesheet it @imports, transitively.

    READS WHAT THE BROWSER READS, which is not the same question as "every
    .css file in the directory". scholar.css is a BARREL -- nine @imports and
    no rules of its own -- so a directory glob happened to agree with the
    import graph. Happened to: a partial moved out of this tree, or one left
    behind and no longer imported, makes them diverge, and the glob is wrong
    in both directions (missing a file the page loads, or counting one it
    does not).

    scitex-ui hit the missing-file half for real: 0.16.0 split colors.css
    into a barrel, and every single-file read of it silently went empty.
    """
    seen = _seen if _seen is not None else set()
    entry = entry.resolve()
    if entry in seen or not entry.exists():
        return ""
    seen.add(entry)
    text = entry.read_text()
    parts = [text]
    for href in _IMPORT_RE.findall(text):
        parts.append(_resolve_css(entry.parent / href, seen))
    return "\n".join(parts)


def _scholar_css() -> str:
    """Everything that can reference a token, as the browser would see it.

    INCLUDES THE TEMPLATE, and that is not incidental. scholar.html carries
    inline styles (it is marked `hook-bypass: inline-style`) with 11
    no-fallback `var()` uses. A scan of only stylesheets answers "do the
    STYLESHEETS resolve" while claiming to answer "does the PAGE resolve".
    """
    return _resolve_css(CSS_ENTRY) + "\n" + TEMPLATE.read_text()


def _theme_css() -> str:
    """scitex-ui's shell/theme.css, read from the INSTALLED package."""
    import scitex_ui

    path = (
        Path(scitex_ui.__file__).parent
        / "static" / "scitex_ui" / "css" / "shell" / "theme.css"
    )
    # Resolved, not read: theme.css is a leaf TODAY. colors.css was a leaf
    # too until 0.16.0 split it into a barrel, at which point every
    # single-file read of it returned almost nothing and looked like a lost
    # token. One release away, for any file.
    return _resolve_css(path)


def _referenced_without_fallback(css: str) -> set:
    """Tokens used as `var(--x)` with NO fallback -- the ones with no safety net."""
    return set(re.findall(r"var\(\s*(--[a-zA-Z0-9-]+)\s*\)", css))


def _declared(css: str) -> set:
    return set(re.findall(r"(--[a-zA-Z0-9-]+)\s*:", css))


def test_token_scan_actually_finds_references():
    """Positive control: an absence assertion below is vacuous without this."""
    # Arrange
    css = _scholar_css()

    # Act
    referenced = _referenced_without_fallback(css)

    # Assert
    assert referenced


def test_token_scan_covers_the_template_too():
    """Control for the template half -- a css-only scan would pass this file's
    other tests while missing every inline `var()` in the rendered page."""
    # Arrange
    template_only = _referenced_without_fallback(TEMPLATE.read_text())

    # Act
    seen_by_scan = _referenced_without_fallback(_scholar_css())

    # Assert
    assert template_only <= seen_by_scan and template_only


def test_every_referenced_token_resolves():
    """No token may reference into nothing -- that renders unstyled, silently."""
    # Arrange
    available = _declared(_scholar_css()) | _declared(_theme_css())

    # Act
    dangling = sorted(_referenced_without_fallback(_scholar_css()) - available)

    # Assert
    assert not dangling, (
        f"referenced with no fallback and declared nowhere: {dangling}. "
        f"Either scholar deleted a token it still uses, or scitex-ui dropped "
        f"one scholar depends on."
    )


@pytest.mark.parametrize("token", SHADOWED_TOKENS)
def test_shadowed_token_comes_from_scitex_ui(token):
    """The seven deleted tokens must still be available -- from upstream."""
    # Arrange
    theme = _theme_css()

    # Act
    declared_upstream = token in _declared(theme)

    # Assert
    assert declared_upstream


@pytest.mark.parametrize("token", SHADOWED_TOKENS)
def test_scholar_does_not_redeclare_shadowed_token(token):
    """Re-adding one silently restores the load-order-dependent collision."""
    # Arrange
    scholar_css = _scholar_css()

    # Act
    redeclared = token in _declared(scholar_css)

    # Assert
    assert not redeclared, (
        f"{token} is declared in scholar's CSS again. It must come from "
        f"scitex-ui's shell/theme.css; redeclaring it means whichever "
        f"stylesheet loads last wins."
    )


def test_template_links_scitex_ui_theme():
    """The tokens are only available if the page actually links the file."""
    # Arrange
    response = views.index(RequestFactory().get("/"))

    # Act
    html = response.content.decode()

    # Assert
    assert "scitex_ui/css/shell/theme.css" in html


# ---------------------------------------------------------------------------
# @import resolution
#
# theme.css is a LEAF today, so the real files cannot demonstrate that the
# resolver follows anything -- a check that cannot exercise its own mechanism
# proves nothing about it. These use a synthetic barrel for the mechanism and
# the real scholar.css for the integration.
# ---------------------------------------------------------------------------


def test_resolver_follows_an_import(tmp_path):
    """The mechanism, on a fixture, because no shipped file exercises it."""
    # Arrange
    (tmp_path / "child.css").write_text(":root { --from-child: #123456; }")
    barrel = tmp_path / "barrel.css"
    barrel.write_text('@import url("child.css");')

    # Act
    resolved = _resolve_css(barrel)

    # Assert
    assert "--from-child" in resolved


def test_resolver_follows_imports_transitively(tmp_path):
    """A barrel of barrels -- 0.16.0's colors.css shape is one level; assume more."""
    # Arrange
    (tmp_path / "leaf.css").write_text(":root { --deep: #abcdef; }")
    (tmp_path / "mid.css").write_text('@import url("leaf.css");')
    root = tmp_path / "root.css"
    root.write_text('@import url("mid.css");')

    # Act
    resolved = _resolve_css(root)

    # Assert
    assert "--deep" in resolved


def test_resolver_survives_an_import_cycle(tmp_path):
    """A cycle must terminate rather than recurse until the stack dies."""
    # Arrange
    a = tmp_path / "a.css"
    b = tmp_path / "b.css"
    a.write_text('@import url("b.css");:root{--from-a:#111;}')
    b.write_text('@import url("a.css");:root{--from-b:#222;}')

    # Act
    resolved = _resolve_css(a)

    # Assert
    assert "--from-b" in resolved


def test_scholar_entry_point_reaches_a_partial_only_token():
    """Integration: scholar.css is a barrel, so this fails if following breaks.

    --bg-monaco is declared ONLY in _partials/_base.css and nowhere in
    scholar.css itself, so its presence proves the entry point was followed
    rather than merely read.
    """
    # Arrange
    entry_text = CSS_ENTRY.read_text()

    # Act
    resolved = _resolve_css(CSS_ENTRY)

    # Assert
    assert "--bg-monaco" in resolved and "--bg-monaco" not in entry_text


# EOF


# ---------------------------------------------------------------------------
# /api/health must report the package version.
#
# WHY THIS EXISTS: "is this deployment running what we shipped?" had no answer
# reachable over HTTP. On 2026-08-23 I tried to answer it by searching the
# rendered page for a version and got a FALSE POSITIVE -- the match was the
# substring inside a CDN url for `highlight.js/11.9.0`, not scholar's version at
# all. A version must be SERVED deliberately, not scraped.
# ---------------------------------------------------------------------------
def test_health_reports_the_package_version():
    # Arrange
    from scitex_scholar import __version__

    from scitex_scholar._django.views import health

    request = RequestFactory().get("/api/health")
    # Act
    payload = json.loads(health(request).content)
    # Assert
    assert payload["version"] == __version__


def test_health_version_is_not_a_placeholder():
    """Control: the field must carry a real version, not an empty string.

    `assert "version" in payload` would pass on `""` or `None`, and an empty
    version reads as "unknown deployment" exactly when someone is trying to
    establish which deployment they are looking at.
    """
    # Arrange
    from scitex_scholar._django.views import health

    request = RequestFactory().get("/api/health")
    # Act
    version = json.loads(health(request).content)["version"]
    # Assert
    assert version and version[0].isdigit(), f"unusable version field: {version!r}"


# --- refuse to serve without our app installed (hub prod 2026-09-05) ---------
#
# The guard runs at IMPORT of `views` against the REAL app registry, so each
# arm is a fresh interpreter that configures a genuine host project and
# imports the module -- no fixture patching, the same shape hub runs. The
# child gets PYTHONPATH pointed at the checkout under test, so it exercises
# the same source the provenance guard in tests/conftest.py verified.

_HOST_TEMPLATE = """
import django
from django.conf import settings
settings.configure(
    SECRET_KEY="test-only",
    INSTALLED_APPS={installed_apps!r},
    TEMPLATES=[{{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}}],
    STATIC_URL="/static/",
)
if {setup!r}:
    django.setup()
import scitex_scholar._django.views as views
print("IMPORTED", views.APP_NAME)
"""

_HOST_APPS = ["django.contrib.contenttypes", "django.contrib.staticfiles", "scitex_ui"]


def _import_views_in_host(installed_apps, setup=True):
    """Run a throwaway host project that imports our views; return the result."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    import scitex_scholar

    src_dir = str(Path(scitex_scholar.__file__).resolve().parent.parent)
    env = {**os.environ, "PYTHONPATH": src_dir}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    code = _HOST_TEMPLATE.format(installed_apps=list(installed_apps), setup=setup)
    return subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120
    )


def test_views_refuse_to_import_when_host_omits_our_app():
    """Negative arm: the host forgot ScholarEditorConfig -> named refusal."""
    # Arrange
    host_apps = _HOST_APPS
    # Act
    result = _import_views_in_host(host_apps)
    # Assert
    assert (result.returncode != 0 and views.APP_CONFIG_PATH in result.stderr), result.stderr[-800:]


def test_views_refusal_names_installed_apps_as_the_place_to_fix():
    """The refusal must say WHERE to add the entry, not only that it is missing."""
    # Arrange
    host_apps = _HOST_APPS
    # Act
    result = _import_views_in_host(host_apps)
    # Assert
    assert "INSTALLED_APPS" in result.stderr, result.stderr[-800:]


def test_views_import_when_host_installs_our_app():
    """Positive control for the arms above: same host, app installed -> imports."""
    # Arrange
    host_apps = [*_HOST_APPS, views.APP_CONFIG_PATH]
    # Act
    result = _import_views_in_host(host_apps)
    # Assert
    assert result.returncode == 0 and "IMPORTED" in result.stdout, result.stderr[-800:]


def test_views_import_stays_silent_when_registry_is_not_ready():
    """Unknown is not "not installed": an importer that runs before django.setup() is not refused."""
    # Arrange
    host_apps = _HOST_APPS
    # Act
    result = _import_views_in_host(host_apps, setup=False)
    # Assert
    assert result.returncode == 0 and "IMPORTED" in result.stdout, result.stderr[-800:]


def test_app_guard_checks_the_app_name_the_config_declares():
    """The guard and apps.py must name the same app, or the guard lies."""
    # Arrange
    from scitex_scholar._django.apps import ScholarEditorConfig

    expected = (ScholarEditorConfig.name, ScholarEditorConfig.__name__)
    # Act
    actual = (views.APP_NAME, views.APP_CONFIG_PATH.rsplit(".", 1)[1])
    # Assert
    assert actual == expected


# EOF
