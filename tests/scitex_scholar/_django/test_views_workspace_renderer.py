"""Prospective genuine leaf renderer/native-index controls; not yet executed."""

from functools import partial

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.middleware.locale import LocaleMiddleware
from django.test import RequestFactory, override_settings
from django.utils import translation

from scitex_scholar._django import views
from tests.scitex_scholar._django.test_views_workspace_content import (
    _body_elements,
    _rendered_dom,
)

pytest_plugins = ("tests.scitex_scholar._django.test_views_shell_context",)


def _leaf_assets(dom):
    """Keep real leaf asset order/attributes and the translated JSON script."""
    return tuple(str(node) for node in dom.select(
        'meta[name="stx-mount"], meta[name="theme-color"], '
        'link[href^="/static/scholar/"], script[src^="/static/scholar/"], '
        'script#SCHOLAR_I18N'
    ))


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("binding", ["bound", "user"])
@pytest.mark.parametrize(
    "trusted_root,native_path,script_prefix,mode",
    [
        ("/", "/", "", "standalone"),
        ("/apps/scholar/v2/", "/apps/scholar/v2/", "", "hub"),
        ("/research/apps/scholar/v2/", "/apps/scholar/v2/", "/research", "hub"),
    ],
    ids=["root", "nested", "script-prefix"],
)
def test_workspace_renderer_conserves_index_at_trusted_root(
    _private_context, language, binding, trusted_root, native_path,
    script_prefix, mode,
):
    # Arrange
    provider = views.ScholarLocalProjectProvider(
        _private_context["paths"]["SCITEX_SCHOLAR_PROJECTS_DIR"]
    )
    results = []
    expected = []
    for username in ("alice", "bob"):
        user = get_user_model()(username=username)
        base = _private_context["paths"]["SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE"]
        if binding == "bound":
            base = _private_context["temp_root"] / "bound-libraries"
        root = (base / username).resolve()
        request = RequestFactory().get(
            native_path, {"project": "Alpha"}, SCRIPT_NAME=script_prefix,
            HTTP_ACCEPT_LANGUAGE=language,
        )
        get_token(request)
        secret = request.META["CSRF_COOKIE"]
        request.COOKIES[settings.CSRF_COOKIE_NAME] = secret
        fragment_request = RequestFactory().get(
            "/workspace/content/scholar/",
            {"project": "Alpha", "mount": "/untrusted/"},
            SCRIPT_NAME=script_prefix, HTTP_ACCEPT_LANGUAGE=language,
            HTTP_COOKIE=f"{settings.CSRF_COOKIE_NAME}={secret}",
        )
        for http_request in (request, fragment_request):
            http_request.user = user
            if binding == "bound":
                http_request.scholar_library_root = root
        before = tuple(views._library_root_for(req) for req in (request, fragment_request))
        with override_settings(SCITEX_APP_MODE=mode), translation.override("en"):
            # Act
            full_response = LocaleMiddleware(CsrfViewMiddleware(views.index))(request)
            renderer = partial(views.render_workspace_content, stx_mount=trusted_root)
            fragment_response = LocaleMiddleware(CsrfViewMiddleware(renderer))(fragment_request)
            full, full_csrf = _rendered_dom(full_response.content.decode(), secret)
            fragment, fragment_csrf = _rendered_dom(fragment_response.content.decode(), secret)
            context = views.index_context(fragment_request)
            results.append({
                "status": (full_response.status_code, fragment_response.status_code),
                "body": _body_elements(fragment),
                "assets": _leaf_assets(fragment),
                "outer_shell": len(fragment.select("html,head,body")),
                "mount": [node["content"] for node in fragment.select('meta[name="stx-mount"]')],
                "language": fragment_response.headers["Content-Language"],
                "library_text": fragment.select_one('[data-tab="library"]').get_text(),
                "csrf": (full_csrf, fragment_csrf),
                "cookie": fragment_response.cookies[settings.CSRF_COOKIE_NAME].value,
                "roots": (before, tuple(views._library_root_for(req) for req in (request, fragment_request))),
                "project": (context["current_project"], context["app_scope"], provider.last_visited(fragment_request)),
            })
            expected.append({
                "status": (200, 200), "body": _body_elements(full),
                "assets": _leaf_assets(full), "outer_shell": 0,
                "mount": [trusted_root.rstrip("/")], "language": language,
                "library_text": {"en": "Library", "ja": "ライブラリ"}[language],
                "csrf": ([True], [True]), "cookie": secret,
                "roots": ((root, root), (root, root)),
                "project": ("Alpha", "user", "Alpha"),
            })
    # Assert
    assert results == expected
