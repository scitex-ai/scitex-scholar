"""New native-index/fragment controls using the genuine private request fixture."""

import re

import pytest
from bs4 import BeautifulSoup, Comment
from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import CsrfViewMiddleware, _does_token_match, get_token
from django.middleware.locale import LocaleMiddleware
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.utils import translation

from scitex_scholar._django import views

pytest_plugins = ("tests.scitex_scholar._django.test_views_shell_context",)

_SCRIPT_NAMES = (
    "stx-mount.js", "app.js", "search.js", "library.js",
    "graph/ForceSimulation.js", "graph/GraphRenderer.js", "graph/citation-graph.js",
)
_CONTENT_IDS = {
    "searchForm", "tab-search", "tab-library", "libraryImportFile",
    "libraryImportBtn", "libraryExportBtn", "graphForm", "tab-graph",
}


def _rendered_dom(html, secret):
    """Ignore comments and normalize only actual cookie-validated CSRF fields."""
    dom = BeautifulSoup(html, "html.parser")
    for comment in dom.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    validations = []
    for field in dom.select('input[type="hidden"][name="csrfmiddlewaretoken"]'):
        token = field.get("value", "")
        valid = (
            re.fullmatch(r"[a-zA-Z0-9]{64}", token) is not None
            and _does_token_match(token, secret)
        )
        validations.append(valid)
        if valid:
            field["value"] = "<cookie-validated-CSRF-mask>"
    return dom, validations


def _body_elements(dom):
    """Compare the two genuine content roots, retaining their inner DOM/text."""
    return tuple(
        str(dom.select_one(selector))
        for selector in (".stx-app-header", ".app-container")
    )


@pytest.mark.parametrize(
    "language,path,mode,username",
    [
        ("en", "/", "standalone", "alice"),
        ("ja", "/", "standalone", "alice"),
        ("en", "/apps/scholar/v2/", "hub", "bob"),
        ("ja", "/apps/scholar/v2/", "hub", "bob"),
    ],
    ids=["en-root", "ja-root", "en-mounted", "ja-mounted"],
)
def test_index_workspace_content_preserves_native_rendering(
    _private_context, language, path, mode, username
):
    # Arrange
    request = RequestFactory().get(
        path, {"project": "Alpha"}, HTTP_ACCEPT_LANGUAGE=language
    )
    request.user = get_user_model()(username=username)
    root_parents = {
        "standalone": _private_context["temp_root"] / "bound-library",
        "hub": _private_context["paths"]["SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE"],
    }
    root = root_parents[mode] / username
    request.scholar_library_root = {"standalone": root, "hub": None}[mode]
    provider = views.ScholarLocalProjectProvider(
        _private_context["paths"]["SCITEX_SCHOLAR_PROJECTS_DIR"]
    )
    get_token(request)
    secret = request.META["CSRF_COOKIE"]
    request.COOKIES[settings.CSRF_COOKIE_NAME] = secret
    root_before = views._library_root_for(request)
    with override_settings(SCITEX_APP_MODE=mode), translation.override("en"):
        # Act
        response = LocaleMiddleware(CsrfViewMiddleware(views.index))(request)
        context = views.index_context(request)
        fragment_html = render_to_string(
            "scholar/workspace_content.html", context, request=request
        )
        full, full_csrf = _rendered_dom(response.content.decode(), secret)
        fragment, fragment_csrf = _rendered_dom(fragment_html, secret)
        result = {
            "status": response.status_code,
            "content_roots": _body_elements(fragment),
            "fragment_outer_or_assets": len(
                fragment.select("html,head,body,script,link,meta")
            ),
            "content_ids": {
                node["id"] for node in fragment.select("[id]")
            } & _CONTENT_IDS,
            "csrf": (full_csrf, fragment_csrf),
            "cookies": (
                request.META["CSRF_COOKIE"],
                response.cookies[settings.CSRF_COOKIE_NAME].value,
            ),
            "languages": (full.html["lang"], response.headers["Content-Language"]),
            "library_text": fragment.select_one('[data-tab="library"]').get_text(),
            "shell_content_panes": len(full.select("main#main-content.ws-module-pane")),
            "scripts": tuple(
                node["src"] for node in full.select("script[src]")
                if node["src"].startswith("/static/scholar/")
            ),
            "stylesheets": [
                node["href"] for node in full.select('link[rel="stylesheet"]')
                if node["href"].startswith("/static/scholar/")
            ],
            "mounts": [node["content"] for node in full.select('meta[name="stx-mount"]')],
            "pwa": [node["href"] for node in full.select('link[rel="manifest"]')],
            "project_scope": (context["current_project"], context["app_scope"]),
            "remembered": provider.last_visited(request),
            "roots": (root_before, views._library_root_for(request)),
        }
        expected = {
            "status": 200,
            "content_roots": _body_elements(full),
            "fragment_outer_or_assets": 0,
            "content_ids": _CONTENT_IDS,
            "csrf": ([True], [True]),
            "cookies": (secret, secret),
            "languages": (language, language),
            "library_text": {"en": "Library", "ja": "ライブラリ"}[language],
            "shell_content_panes": 1,
            "scripts": tuple("/static/scholar/js/" + name for name in _SCRIPT_NAMES),
            "stylesheets": ["/static/scholar/css/scholar.css"],
            "mounts": [path.rstrip("/")],
            "pwa": ["/static/scholar/pwa/manifest.json"],
            "project_scope": ("Alpha", "user"),
            "remembered": "Alpha",
            "roots": (root.resolve(), root.resolve()),
        }
        # Assert
        assert result == expected
