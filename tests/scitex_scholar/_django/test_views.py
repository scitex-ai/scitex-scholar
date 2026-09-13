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
import os
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


@override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None)
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


@override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None)
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


@override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None)
def test_graph_paper_returns_503_with_no_api_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/paper?doi=10.1038/s41586-020-2008-3")
    # Act
    resp = views.graph_paper(request)
    # Assert
    assert resp.status_code == 503


@override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None)
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
# child gets the checkout PREPENDED to PYTHONPATH, so it exercises the same
# source the provenance guard in tests/conftest.py verified -- while still
# inheriting whatever else PYTHONPATH was carrying, which in some CI images
# is where the dependencies themselves live.

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
import os as _os
_marker = _os.environ.get("SCITEX_TEST_MARKER")
if _marker:
    __import__(_marker)
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
    # PREPEND, never REPLACE. Some environments deliver dependencies THROUGH
    # PYTHONPATH rather than installing them into the interpreter -- the
    # release job runs the suite inside an apptainer image whose deps are
    # "layered, not on the bare runner". Overwriting PYTHONPATH there deleted
    # django from the child, and these four tests failed with
    # ModuleNotFoundError while the parent process imported django fine.
    #
    # It passed locally and on every PR, because in those environments the
    # deps live in the venv and PYTHONPATH carries nothing -- so replacing it
    # cost nothing. The release gate was the only place the difference showed,
    # and it is the reason 1.11.0 halted before publishing rather than after.
    inherited = os.environ.get("PYTHONPATH", "")
    env = {
        **os.environ,
        "PYTHONPATH": f"{src_dir}{os.pathsep}{inherited}" if inherited else src_dir,
    }
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


# --- the crossref endpoint setting is namespaced; bare name is a loud alias --
#
# A host (scitex-hub) defines this setting in ITS settings module, so the
# leaf's name must be namespaced. The bare spelling is honoured for one
# release and warns once per process. `override_settings` is Django's own
# test-time settings mechanism, not a mock: the view reads the real settings
# object, and each test restores it on exit.


def test_api_url_reads_the_namespaced_setting():
    """The documented name works on its own."""
    # Arrange
    from django.test import override_settings

    with override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL="http://ns.example:3333"):
        # Act
        resolved = views._api_url()
    # Assert
    assert resolved == "http://ns.example:3333"


def test_api_url_honours_the_deprecated_bare_setting_for_one_release():
    """A host still on the pre-1.11 spelling keeps working during the window."""
    # Arrange
    from django.test import override_settings

    with override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None, CROSSREF_API_URL="http://bare.example:3333"):
        # Act
        resolved = views._api_url()
    # Assert
    assert resolved == "http://bare.example:3333"


def test_api_url_prefers_the_namespaced_setting_when_both_are_set():
    """Precedence: the documented name must be the one that wins."""
    # Arrange
    from django.test import override_settings

    with override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL="http://ns.example:3333", CROSSREF_API_URL="http://bare.example:3333"):
        # Act
        resolved = views._api_url()
    # Assert
    assert resolved == "http://ns.example:3333"


def test_api_url_warns_when_the_deprecated_bare_setting_is_used(caplog):
    """The alias is LOUD: one warning naming both spellings and the removal release."""
    # Arrange
    import logging

    from django.test import override_settings

    views._warned_deprecated_setting = False
    caplog.set_level(logging.WARNING, logger=views.__name__)
    with override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None, CROSSREF_API_URL="http://bare.example:3333"):
        # Act
        views._api_url()
    # Assert
    assert all(
        token in caplog.text
        for token in ("CROSSREF_API_URL", "SCITEX_SCHOLAR_CROSSREF_API_URL", "deprecated", views._CROSSREF_ALIAS_REMOVAL)
    ), caplog.text


def test_standalone_settings_define_only_the_namespaced_name():
    """The leaf's own settings module must not keep the alias alive."""
    # Arrange
    from django.conf import settings

    # Act
    defined = (hasattr(settings, "SCITEX_SCHOLAR_CROSSREF_API_URL"), hasattr(settings, "CROSSREF_API_URL"))
    # Assert
    assert defined == (True, False)


# --- the 503 body must carry the FIX, not only the symptom -------------------
#
# Measured 2026-09-02 as a standalone first-run blocker: the citation graph
# answers 503 and the old body said only "CrossRef API not configured", so a
# first-time user learned what broke and not what to do. The status was always
# right; the body was half an answer.

GRAPH_ROUTES_THAT_NEED_AN_ENDPOINT = (
    ("graph_network", "/api/graph/network", {"doi": "10.1000/x"}),
    ("graph_related", "/api/graph/related", {"doi": "10.1000/x"}),
    ("graph_paper", "/api/graph/paper", {"doi": "10.1000/x"}),
    ("graph_health", "/api/graph/health", {}),
)


def _unconfigured_response(view_name: str, path: str, params: dict):
    """Call one graph view with no endpoint configured; return its parsed body."""
    from django.test import override_settings

    with override_settings(SCITEX_SCHOLAR_CROSSREF_API_URL=None, CROSSREF_API_URL=None):
        request = RequestFactory().get(path, params)
        response = getattr(views, view_name)(request)
    return response, json.loads(response.content)


@pytest.mark.parametrize("view_name,path,params", GRAPH_ROUTES_THAT_NEED_AN_ENDPOINT)
def test_unconfigured_graph_route_names_the_setting_to_set(view_name, path, params):
    """Every 503 must name the variable whose absence caused it."""
    # Arrange
    expected = views.CROSSREF_API_URL_SETTING
    # Act
    _, body = _unconfigured_response(view_name, path, params)
    # Assert
    assert expected in body.get("fix", ""), body


@pytest.mark.parametrize("view_name,path,params", GRAPH_ROUTES_THAT_NEED_AN_ENDPOINT)
def test_unconfigured_graph_route_says_what_to_do_next(view_name, path, params):
    """A 503 that only states the symptom is half-written (constitution §2)."""
    # Arrange
    required_keys = {"error", "detail", "fix", "setting"}
    # Act
    _, body = _unconfigured_response(view_name, path, params)
    # Assert
    assert required_keys <= set(body), body


@pytest.mark.parametrize("view_name,path,params", GRAPH_ROUTES_THAT_NEED_AN_ENDPOINT)
def test_unconfigured_graph_route_still_answers_503(view_name, path, params):
    """The status code is the contract consumers branch on; it must not move."""
    # Arrange
    expected = 503
    # Act
    response, _ = _unconfigured_response(view_name, path, params)
    # Assert
    assert response.status_code == expected


def test_graph_health_keeps_its_status_field_alongside_the_fix():
    """graph_health's own shape survives: callers read `status`, not `error`."""
    # Arrange
    expected = "unhealthy"
    # Act
    _, body = _unconfigured_response("graph_health", "/api/graph/health", {})
    # Assert
    assert body.get("status") == expected


def test_the_four_routes_give_one_explanation_not_four():
    """One shared payload: four routes must not drift into four stories."""
    # Arrange
    bodies = [
        _unconfigured_response(name, path, params)[1]
        for name, path, params in GRAPH_ROUTES_THAT_NEED_AN_ENDPOINT
    ]
    # Act
    fixes = {body["fix"] for body in bodies}
    # Assert
    assert len(fixes) == 1, fixes


def test_the_503_docs_pointer_names_a_file_that_exists():
    """A pointer to documentation that is not there is the defect being fixed.

    The first draft of this payload cited a README anchor (`#citation-graph`)
    that no heading produced. Shipping it would have made the error message a
    third instance of the week's pattern: an explanation that sends the reader
    somewhere the thing is not.
    """
    # Arrange
    repo_root = next(
        p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()
    )
    # Act
    referenced = repo_root / views._not_configured_payload()["docs"]
    # Assert
    assert referenced.is_file(), referenced


def test_host_subprocess_inherits_an_existing_pythonpath(tmp_path):
    """The child must KEEP what PYTHONPATH already carried, not just get src/.

    REGRESSION, and it cost a release. The helper above built the child's
    environment as {**os.environ, "PYTHONPATH": src_dir} -- a REPLACEMENT. In
    environments that deliver DEPENDENCIES through PYTHONPATH rather than
    installing them into the interpreter (the release job runs the suite in an
    apptainer image whose deps are "layered, not on the bare runner"), that
    deleted django from the child, and the four host-subprocess tests failed
    with ModuleNotFoundError while the parent imported django perfectly well.

    It passed locally and on every PR because in those environments PYTHONPATH
    is empty, so replacing it costs nothing -- the defect was invisible
    everywhere except the one environment that layers deps. This test makes it
    visible everywhere: it puts a marker module on PYTHONPATH, and the child
    script itself imports that marker (via SCITEX_TEST_MARKER), so the
    inheritance is asserted by the child, not inferred by the parent.

    The env var is set on the real environment and restored by hand (the
    idiom this repo's other env tests use), not via a patch fixture: the whole
    point of the test is that a REAL child process inherits a REAL value, and
    a patched view of it would be testing the patch, not the inheritance.
    """
    # Arrange
    (tmp_path / "pythonpath_marker.py").write_text("VALUE = 'inherited'\n")
    prior = os.environ.get("PYTHONPATH")
    # PREPEND the marker dir to whatever PYTHONPATH already carried. In the
    # release image the real deps (django included) are layered ONTO PYTHONPATH;
    # replacing it here would make THIS test commit the very clobbering bug under
    # test -- the child would lose django. Prepending keeps the layered deps and
    # adds the marker. The child then imports the marker (via SCITEX_TEST_MARKER),
    # so "the child sees what was already on PYTHONPATH" is asserted, not assumed.
    os.environ["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{prior}" if prior else str(tmp_path)
    os.environ["SCITEX_TEST_MARKER"] = "pythonpath_marker"
    try:
        # Act
        result = _import_views_in_host([*_HOST_APPS, views.APP_CONFIG_PATH])
    finally:
        if prior is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = prior
        os.environ.pop("SCITEX_TEST_MARKER", None)
    # Assert
    assert result.returncode == 0, result.stderr[-800:]


# ---------------------------------------------------------------------------
# Compass 2026-09-10, Scholar search-UX structure.
#
# Regression guards for the search-first rework of the standalone Django GUI
# (compass-impl-scitex-scholar-20260910). They assert STRUCTURE, not pixels:
# render the template via views.index or read the shipped CSS/JS directly and
# pin the DOM the page ships, so a future edit that reintroduces the old
# layout fails here. One assertion per test, AAA-marked, matching this file's
# convention (and the PA-307 §3 audit rule).
#
#   L303 Search is the primary, default tab; 44px touch target on the input.
#   L653 Advanced query syntax collapsed; cache + source + CrossRef status out
#        of the always-visible sidebar into a collapsed "Advanced" section.
#   L316 Placeholder tabs share the same container as content tabs (no jump).
#   L345 Each search result with a DOI offers "Build citation graph".
# ---------------------------------------------------------------------------

COMPASS_CSS_DIR = Path(views.__file__).parent / "static" / "scholar" / "css" / "_partials"
COMPASS_SEARCH_JS = Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
COMPASS_TEMPLATE = TEMPLATE


def _compass_index_body() -> str:
    """Render the standalone index; the browser's HTML is the thing under test."""
    return views.index(RequestFactory().get("/")).content.decode()


def test_search_is_the_default_active_tab():
    # Arrange
    body = _compass_index_body()
    # Act
    search_default = 'class="tab-btn active" data-tab="search"' in body
    search_panel_active = 'id="tab-search" class="tab-panel active"' in body
    # Assert
    assert search_default and search_panel_active


def test_graph_tab_is_not_default_but_still_present():
    # Arrange
    body = _compass_index_body()
    # Act
    graph_present = 'data-tab="graph"' in body
    graph_not_default = 'class="tab-btn active" data-tab="graph"' not in body
    graph_panel_not_active = 'id="tab-graph" class="tab-panel active"' not in body
    # Assert
    assert graph_present and graph_not_default and graph_panel_not_active


def test_advanced_section_is_collapsed_by_default():
    # Arrange
    body = _compass_index_body()
    # Act
    present = "search-advanced" in body
    closed_on_load = '<details class="search-advanced">' in body  # no open attr
    # Assert
    assert present and closed_on_load


def test_advanced_hides_query_syntax_until_requested():
    # Arrange
    body = _compass_index_body()
    # Act
    syntax_block = "search-advanced__syntax" in body
    impact_factor_syntax = "if:&gt;5" in body  # escaped in the template
    # Assert
    assert syntax_block and impact_factor_syntax


def test_ignore_cache_and_source_are_wired_to_the_api():
    # Arrange
    body = _compass_index_body()
    js = COMPASS_SEARCH_JS.read_text()
    # Act
    checkbox_present = 'id="searchNoCache"' in body
    forwards_no_cache = 'params.set("no_cache", "true")' in js
    forwards_mode = 'params.set("mode", modeSelect.value)' in js
    # Assert
    assert checkbox_present and forwards_no_cache and forwards_mode


def test_crossref_api_status_moved_out_of_the_sidebar():
    # Arrange
    body = _compass_index_body()
    # Act
    in_advanced = "search-advanced__api" in body
    not_a_sidebar_section = 'sidebar-section__title">CrossRef API</span>' not in body
    # Assert
    assert in_advanced and not_a_sidebar_section


def test_search_and_library_content_share_one_container_class():
    # Arrange
    # #101: "keep primary content/header geometry stable when moving between
    # Search and Library." The two tabs render different inner content (a
    # search form vs a centered placeholder), but they must be inset by the
    # SAME wrapper so their left edge, width and top origin match. That is what
    # the real browser measured (search card and library placeholder both at
    # x=256/w=1168 desktop, x=16/w=358 mobile) — both are children of a
    # .citation-graph-container. This pins that shared-wrapper contract for
    # BOTH tabs, not just the placeholder.
    tpl = COMPASS_TEMPLATE.read_text()
    # Act
    def _panel_wraps_container(panel_id: str) -> bool:
        start = tpl.index(f'id="{panel_id}"')
        # next panel boundary (or end of file)
        nxt = [tpl.index(f'id="tab-{t}"') for t in ("search", "library", "graph")
               if f'id="tab-{t}"' != panel_id and tpl.find(f'id="tab-{t}"') > start]
        end = min(nxt) if nxt else len(tpl)
        region = tpl[start:end]
        return "citation-graph-container" in region
    search_wraps = _panel_wraps_container('tab-search')
    library_wraps = _panel_wraps_container('tab-library')
    # Assert
    assert search_wraps and library_wraps


def test_search_results_offer_build_citation_graph():
    # Arrange
    js = COMPASS_SEARCH_JS.read_text()
    css = (COMPASS_CSS_DIR / "_search.css").read_text()
    # Act
    action_in_js = "Build citation graph" in js
    styled = ".search-result__graph-btn" in css
    # Assert
    assert action_in_js and styled


def test_search_input_has_a_44px_touch_target():
    # Arrange
    forms_css = (COMPASS_CSS_DIR / "_forms.css").read_text()
    base_css = (COMPASS_CSS_DIR / "_base.css").read_text()
    # Act
    # #93: the search input is sized via a scholar-owned token (declared in
    # _base.css, always linked) rather than a raw px or an unlinked scitex-ui
    # --input-height fallback. The token must be declared AND referenced.
    token_declared = "--scholar-search-height" in base_css
    token_referenced = "min-height: var(--scholar-search-height)" in forms_css
    no_raw_fallback = "var(--input-height, 44px)" not in forms_css
    # Assert
    assert token_declared and token_referenced and no_raw_fallback


# --- item 116/115/114: "Search" must say WHERE it searches ------------------
#
# Compass 2026-09-10: a bare "Search" label does not tell a researcher whether
# they are querying the external databases or their own library -- and the
# library does not exist yet. The tab and the submit button now read
# "Search databases" and the description names the external databases and
# contrasts them with the Library tab.
# ---------------------------------------------------------------------------


def test_search_tab_and_button_are_labelled_databases():
    # Arrange
    body = _compass_index_body()
    # Act
    tab_label = 'class="tab-btn active" data-tab="search">Search databases<' in body
    button_label = 'class="btn-build">Search databases<' in body
    # Assert
    assert tab_label and button_label


def test_search_description_clarifies_external_databases_not_library():
    # Arrange
    body = _compass_index_body()
    # Act
    # The description must both name the external databases and contrast them
    # with the Library so the two surfaces are not confused.
    names_external = "external databases" in body
    contrasts_library = "not your Library" in body
    # Assert
    assert names_external and contrasts_library


# --- TODO 105 / L337: Metadata Enrichment is no longer a top-level tab -------
#
# Small operations must not be promoted to top-level navigation; enrichment
# moves inside the Library surface (TODO 106, a separate, Library-dependent
# build). This pins the absence so a future edit that re-adds the tab fails
# here rather than silently regressing.
# ---------------------------------------------------------------------------


def test_enrichment_is_not_a_top_level_tab():
    # Arrange
    body = _compass_index_body()
    # Act
    no_button = 'data-tab="enrichment"' not in body
    no_panel = 'id="tab-enrichment"' not in body
    no_placeholder_heading = "Metadata Enrichment" not in body
    # Assert
    assert no_button and no_panel and no_placeholder_heading


def test_scholar_tab_bar_has_exactly_three_tabs():
    # Arrange
    body = _compass_index_body()
    # Act
    tab_count = body.count('class="tab-btn')
    # Assert
    assert tab_count == 3


# --- responsive fix (MONITOR-1731): shell side panes + mobile collapse -------
#
# The scitex-ui workspace shell renders Console/Files/Viewer side panes around
# the app content. Scholar has no content for them; leaving them enabled
# produced the empty desktop left gutter and the broken mobile reflow (the
# shell reflows its panes, which then collide with scholar's own two-column
# .app-container). The fix has two halves: declare the panes unused in
# views.index, and collapse scholar's .app-container to one column below 768px.
# ---------------------------------------------------------------------------


def test_index_declares_shell_side_panes_unused():
    # Arrange
    from scitex_scholar._django.views import index

    # Act
    rendered = index(RequestFactory().get("/")).content.decode()
    # The unused panes carry the shell's `ws-pane-unused` class; all three
    # (AI/Console, Files, Viewer) must be present so the shell hides them.
    declares_unused = rendered.count("ws-pane-unused") >= 3
    # Assert
    assert declares_unused


def test_layout_css_collapses_to_one_column_on_mobile():
    # Arrange
    layout_css = (COMPASS_CSS_DIR / "_layout.css").read_text()
    # Act
    has_breakpoint = "@media (max-width: 768px)" in layout_css
    stacks_container = ".app-container" in layout_css and "flex-direction: column" in layout_css
    hides_sidebar = ".app-sidebar" in layout_css and "display: none" in layout_css
    # Assert
    assert has_breakpoint and stacks_container and hides_sidebar


def test_search_form_row_stacks_on_mobile():
    # Arrange
    # #93: a larger search input makes the input + button + results row overflow
    # a 390px viewport, so the row must stack vertically below the breakpoint.
    layout_css = (COMPASS_CSS_DIR / "_layout.css").read_text()
    # Act
    in_mobile_block = "@media (max-width: 768px)" in layout_css
    stacks_form_row = ".form-row" in layout_css and "flex-direction: column" in layout_css
    input_can_shrink = "min-width: 0" in layout_css
    # Assert
    assert in_mobile_block and stacks_form_row and input_can_shrink


# ---------------------------------------------------------------------------
# #106: metadata enrichment as a contextual Library operation.
#
# Enrichment is an action ON a library item (a per-row button in the Library
# tab), NOT a top-level tab (#105 kept it off the nav). The two API routes are
# thin adapters over the package's own storage + enrichment layer; the tests
# below exercise them end-to-end against a temporary, user-scoped library with
# a deterministic offline enrichment fake (PA-306: the pipeline is a
# parameter, not a monkeypatch; the env var is set/restored by hand, not via
# the monkeypatch fixture). No network, no user data.
# ---------------------------------------------------------------------------

import contextlib
import json as _json


@contextlib.contextmanager
def _library_env(root: Path):
    """Point the view's library (and its backing store) at a temp root,
    restoring both on exit. The sanctioned env-var yield pattern, not
    monkeypatch."""
    old_dir = os.environ.get("SCITEX_DIR")
    old_root = os.environ.get("SCITEX_SCHOLAR_LIBRARY_ROOT")
    os.environ["SCITEX_DIR"] = str(root / ".scitex")
    os.environ["SCITEX_SCHOLAR_LIBRARY_ROOT"] = str(root)
    try:
        yield
    finally:
        if old_dir is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = old_dir
        if old_root is None:
            os.environ.pop("SCITEX_SCHOLAR_LIBRARY_ROOT", None)
        else:
            os.environ["SCITEX_SCHOLAR_LIBRARY_ROOT"] = old_root


def _seed_library(root: Path, paper_id: str = "PID1",
                  doi: str = "10.1/example", title: str = "A paper",
                  year: int = 2024, abstract: str = None,
                  authors: list = None) -> Path:
    """Create one master entry; return its metadata.json path."""
    entry = root / "MASTER" / paper_id
    entry.mkdir(parents=True, exist_ok=True)
    basic = {"title": title, "year": year}
    if abstract is not None:
        basic["abstract"] = abstract
    if authors is not None:
        basic["authors"] = authors
    meta = {"metadata": {"id": {"doi": doi}, "basic": basic}}
    path = entry / "metadata.json"
    path.write_text(_json.dumps(meta))
    return path


class _OfflineEnrich:
    """Deterministic offline enrichment fake (hand-rolled, no network).

    Sets a fixed abstract + citation count so the persistence assertion is
    exact. Stands in for ScholarPipelineMetadataSingle via the view's
    `_pipeline` injection seam."""

    async def enrich_paper_async(self, paper, force: bool = False):
        paper.metadata.basic.abstract = "OFFLINE FAKE ABSTRACT"
        paper.metadata.citation_count.total = 7
        return paper


def test_library_list_returns_user_papers(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        meta = _seed_library(tmp_path, abstract=None)
        rf = RequestFactory()
        # Act
        resp = views.library_list(rf.get("/api/library"))
        data = _json.loads(resp.content)
        # Assert
        listed = data["papers"]
        assert (
            data["count"] == 1
            and listed[0]["paper_id"] == "PID1"
            and listed[0]["doi"] == "10.1/example"
            and listed[0]["title"] == "A paper"
            and meta.is_file()
        )


def test_library_list_empty_when_no_master(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act
        data = _json.loads(views.library_list(rf.get("/api/library")).content)
        # Assert
        assert data["papers"] == [] and data["count"] == 0


def test_library_enrich_persists_metadata(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        meta_path = _seed_library(tmp_path, abstract=None)
        rf = RequestFactory()
        req = rf.post("/api/library/enrich", {"paper_id": "PID1"})
        # Act — inject the deterministic offline pipeline (no network).
        resp = views.library_enrich(req, _pipeline=_OfflineEnrich())
        data = _json.loads(resp.content)
        reloaded = _json.loads(meta_path.read_text())["metadata"]["basic"]
        # Assert — the enriched metadata is written back to the SAME user-scope
        # master record (abstract now present, citation count persisted).
        assert (
            data["ok"] is True
            and data["abstract_chars"] == len("OFFLINE FAKE ABSTRACT")
            and reloaded["abstract"] == "OFFLINE FAKE ABSTRACT"
        )


def test_library_enrich_requires_paper_id(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act
        resp = views.library_enrich(rf.post("/api/library/enrich", {}))
        # Assert
        assert resp.status_code == 400


def test_library_enrich_404_for_unknown_paper(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        _seed_library(tmp_path, paper_id="KNOWN")
        rf = RequestFactory()
        # Act
        resp = views.library_enrich(rf.post("/api/library/enrich", {"paper_id": "MISSING"}))
        # Assert
        assert resp.status_code == 404


def test_enrichment_is_a_contextual_library_action_not_a_tab():
    # Arrange
    # #106 + #105: enrichment is a per-row action inside the Library tab, never
    # a top-level tab. The tab bar is unchanged (3 tabs), the Library panel
    # carries the list + Enrich wiring, and the JS posts to the enrich route.
    body = _compass_index_body()
    tpl = COMPASS_TEMPLATE.read_text()
    js = (COMPASS_SEARCH_JS.parent / "library.js").read_text()
    # Act
    no_enrich_tab = 'data-tab="enrichment"' not in body
    library_has_list = 'id="libraryList"' in tpl and 'class="library-list"' in tpl
    js_wires_enrich = "api/library/enrich" in js and 'method: "POST"' in js
    # Assert
    assert no_enrich_tab and library_has_list and js_wires_enrich


def test_library_api_routes_are_registered():
    # Arrange
    from django.urls import resolve
    # Act
    listed = resolve("/api/library").func.__name__
    enriched = resolve("/api/library/enrich").func.__name__
    exported = resolve("/api/library/export").func.__name__
    imported = resolve("/api/library/import").func.__name__
    # Assert
    assert (
        listed == "library_list"
        and enriched == "library_enrich"
        and exported == "library_export"
        and imported == "library_import"
    )


# --- #106 / L327: Library Import / Export -----------------------------------
#
# Thin adapters over the package's own BibTeX handler + formatter. Export
# serializes the user's local library (bibtex/ris/endnote); import parses
# BibTeX and persists it to the same MASTER/<id>/metadata.json the list route
# reads. Offline: no network, user-scoped via the env-seam temp root.
# ---------------------------------------------------------------------------


_SAMPLE_BIB = (
    "@article{imp1,\n"
    " title = {Imported Paper Title},\n"
    " author = {Jane Importer and John Second},\n"
    " year = {2022},\n"
    " journal = {Journal of Imports},\n"
    " doi = {10.9/imported}\n"
    "}\n"
)


def test_library_export_bibtex_round_trips_the_library(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        _seed_library(tmp_path, paper_id="XP1", doi="10.2/exported",
                      title="Exported Paper Title", year=2021)
        rf = RequestFactory()
    # Act
    with _library_env(tmp_path):
        resp = views.library_export(rf.get("/api/library/export", {"format": "bibtex"}))
        body = resp.content.decode()
    # Assert
    assert resp.status_code == 200 and "Exported Paper Title" in body and "10.2/exported" in body


def test_library_export_ris_format(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        _seed_library(tmp_path, paper_id="XR1", doi="10.3/ris",
                      title="RIS Paper Title", year=2020)
        rf = RequestFactory()
    # Act
    with _library_env(tmp_path):
        resp = views.library_export(rf.get("/api/library/export", {"format": "ris"}))
        body = resp.content.decode()
    # Assert
    assert resp.status_code == 200 and "RIS Paper Title" in body


def test_library_export_rejects_unsupported_format(tmp_path):
    # Arrange
    rf = RequestFactory()
    # Act
    with _library_env(tmp_path):
        resp = views.library_export(rf.get("/api/library/export", {"format": "csljson"}))
    # Assert
    assert resp.status_code == 400


def test_library_import_bibtex_makes_paper_visible(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act — import a BibTeX entry, then list the library.
        imported = _json.loads(views.library_import(rf.post(
            "/api/library/import", {"format": "bibtex", "bibtex": _SAMPLE_BIB}
        )).content)
        listed = _json.loads(views.library_list(rf.get("/api/library")).content)
        titles = [p.get("title") for p in listed["papers"]]
    # Assert — the imported paper is parsed, persisted, and listed.
    assert imported["ok"] is True and imported["imported"] == 1 and "Imported Paper Title" in titles


def test_library_import_requires_bibtex_body(tmp_path):
    # Arrange
    rf = RequestFactory()
    # Act
    with _library_env(tmp_path):
        resp = views.library_import(rf.post("/api/library/import", {"format": "bibtex"}))
    # Assert
    assert resp.status_code == 400


def test_library_import_rejects_unsupported_format(tmp_path):
    # Arrange
    rf = RequestFactory()
    # Act
    with _library_env(tmp_path):
        resp = views.library_import(rf.post("/api/library/import",
                                            {"format": "ris", "bibtex": _SAMPLE_BIB}))
    # Assert
    assert resp.status_code == 400


def test_library_template_has_import_export_controls():
    # Arrange
    tpl = COMPASS_TEMPLATE.read_text()
    js = (COMPASS_SEARCH_JS.parent / "library.js").read_text()
    # Act
    has_controls = (
        'id="libraryExportBtn"' in tpl
        and 'id="libraryImportBtn"' in tpl
        and 'id="libraryExportFormat"' in tpl
    )
    js_wires_both = "api/library/export" in js and "api/library/import" in js
    # Assert
    assert has_controls and js_wires_both


# --- #162 review fixes: author fidelity, import path-safety, user isolation --

_AUTHORS = ["Jane Importer", "John Second"]


def test_library_export_carries_authors_in_every_format(tmp_path):
    # Arrange
    with _library_env(tmp_path):
        _seed_library(tmp_path, paper_id="AUTH1", doi="10.4/authors",
                      title="Authored Paper", year=2022, authors=list(_AUTHORS))
        rf = RequestFactory()
    # Act
    out = {}
    with _library_env(tmp_path):
        for fmt in ("bibtex", "ris", "endnote"):
            resp = views.library_export(rf.get("/api/library/export", {"format": fmt}))
            out[fmt] = resp.content.decode()
    # Assert -- the exact author names must appear in EVERY supported format
    # (BibTeX joins with " and "; RIS/EndNote split it into separate lines, so
    # each name is present verbatim in all three).
    assert all("Jane Importer" in b and "John Second" in b for b in out.values()), out


def test_library_import_parses_payloads_as_content_not_paths(tmp_path):
    # Arrange
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-FILE-CONTENT-MUST-NOT-APPEAR")
    # Payloads that papers_from_bibtex's auto-detection would misread as paths
    # (a slash, a backslash, a path-like token) but are valid BibTeX content.
    payloads = [
        "@article{a,\n title={S1},\n url={http://x/y/z}\n}\n",
        "@article{b,\n title={B1},\n doi={10.9/back\\\\slash}\n}\n",
        "@article{c,\n title={P1},\n doi={10.9/./rel}\n}\n",
    ]
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act
        results = []
        for bib in payloads:
            resp = views.library_import(
                rf.post("/api/library/import", {"format": "bibtex", "bibtex": bib})
            )
            results.append(_json.loads(resp.content))
        blob = _json.dumps(_json.loads(views.library_list(rf.get("/api/library")).content))
    # Assert -- all three parsed as content, 3 papers total, and the secret
    # server file was never read into the import.
    assert (
        all(r["imported"] == 1 for r in results)
        and sum(r["imported"] for r in results) == 3
        and "TOP-SECRET-FILE-CONTENT-MUST-NOT-APPEAR" not in blob
        and str(secret) not in blob
    ), results


def test_library_isolated_between_two_mounted_users(tmp_path):
    # Arrange
    root_a, root_b = tmp_path / "user_a", tmp_path / "user_b"
    rf = RequestFactory()

    class _User:
        def __init__(self, name):
            self.username = name
            self.is_authenticated = True
            self.is_anonymous = lambda: False

    def _req(path, data=None, user_root=None):
        # POST when a body is supplied, otherwise GET.
        r = rf.post(path, data or {}) if data else rf.get(path)
        if user_root is not None:
            r.user = _User(user_root.name)
            r.scholar_library_root = str(user_root)
        return r

    # Act
    a_root = views._library_root_for(_req("/api/library", user_root=root_a))
    b_root = views._library_root_for(_req("/api/library", user_root=root_b))
    # Bound roots drive both save (PaperIO at root/MASTER) and read (collect_rows),
    # so no global env is needed -- this is the real mounted-user flow.
    views.library_import(
        _req("/api/library/import",
             {"format": "bibtex",
              "bibtex": "@article{aa,\n title={A only},\n doi={10.a/1}\n}\n"},
             user_root=root_a))
    a_papers = _json.loads(views.library_list(_req("/api/library", user_root=root_a)).content)["papers"]
    a_exp = views.library_export(_req("/api/library/export?format=bibtex", user_root=root_a)).content.decode()
    b_papers = _json.loads(views.library_list(_req("/api/library", user_root=root_b)).content)["papers"]
    b_exp = views.library_export(_req("/api/library/export?format=bibtex", user_root=root_b)).content.decode()
    # Assert -- user A's paper is invisible to user B (list + export isolation).
    a_has = any(p["title"] == "A only" for p in a_papers)
    b_has = any(p["title"] == "A only" for p in b_papers)
    assert (
        a_root != b_root
        and a_root.name == "user_a"
        and b_root.name == "user_b"
        and a_has
        and not b_has
        and "A only" in a_exp
        and "A only" not in b_exp
    ), (a_root, b_root, a_papers, b_papers)


def test_assert_safe_library_id_rejects_unsafe_components():
    # Arrange
    bad = ["../escape", "a/b", "a\\b", "a\x00b", "..", ".", ""]

    def _rejects(x):
        try:
            views._assert_safe_library_id(x)
            return False
        except ValueError:
            return True

    # Act
    rejected = [x for x in bad if _rejects(x)]
    accepted = views._assert_safe_library_id("AB12CD34")
    # Assert
    assert rejected == bad and accepted == "AB12CD34"


def test_library_import_view_is_not_csrf_exempt():
    # Arrange
    # Act
    exempt = getattr(views.library_import, "csrf_exempt", False)
    # Assert -- the view must NOT opt out of CSRF (that would weaken the
    # mounted route); protection comes from the host's CsrfViewMiddleware.
    assert exempt is False


def test_library_import_is_csrf_protected_but_token_path_works(tmp_path):
    # Arrange
    # Model the mounted Hub: add CsrfViewMiddleware (the standalone settings
    # carry none, so a token-less POST would otherwise pass) and use a Client
    # that enforces CSRF. Render the index to obtain the csrftoken cookie --
    # the {% csrf_token %} tag in scholar.html now pulls it, which is exactly
    # the value the Library Import JS will send back as X-CSRFToken.
    from django.conf import settings as _s
    from django.test import Client

    mw = list(_s.MIDDLEWARE)
    if "django.middleware.csrf.CsrfViewMiddleware" not in mw:
        if "django.middleware.security.SecurityMiddleware" in mw:
            mw.insert(mw.index("django.middleware.security.SecurityMiddleware") + 1,
                      "django.middleware.csrf.CsrfViewMiddleware")
        else:
            mw.insert(0, "django.middleware.csrf.CsrfViewMiddleware")

    with _library_env(tmp_path / "user"), override_settings(MIDDLEWARE=mw):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get("/")  # index renders {% csrf_token %} -> sets cookie
        cookie = csrf_client.cookies.get("csrftoken")
        token = cookie.value if cookie else ""
        bibtex = "@article{c,\n title={CSRF Test},\n doi={10.5/csrf}\n}\n"
        # Act
        no_token = csrf_client.post(
            "/api/library/import", {"format": "bibtex", "bibtex": bibtex}
        )
        with_token = csrf_client.post(
            "/api/library/import",
            {"format": "bibtex", "bibtex": bibtex},
            HTTP_X_CSRFTOKEN=token,
        )
    # Assert -- cookie set, token-less POST rejected (CSRF intact), token POST
    # succeeds and imports the paper.
    assert (
        bool(cookie)
        and no_token.status_code == 403
        and with_token.status_code == 200
        and _json.loads(with_token.content)["imported"] == 1
    ), (no_token.status_code, with_token.status_code, with_token.content)


# EOF
