#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused SDK shell-context and private request-root controls.

Requests use the real LocaleMiddleware, leaf index, shared UI template and
primary metadata files. The focused runner configures Django's dummy backend
before setup and excludes the global coverage-shim conftest; this module also
keeps its requests on that backend. No migrations or derived Store are used.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
from contextlib import contextmanager

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.test import RequestFactory, override_settings
from django.urls import resolve
from django.utils import translation

from scitex_scholar._django import views
from scitex_scholar.core import Paper
from scitex_scholar.storage.PaperIO import PaperIO


@contextmanager
def _private_environment(paths):
    """Restore every environment value after using only temporary paths."""
    previous = {name: os.environ.get(name) for name in paths}
    for name, path in paths.items():
        os.environ[name] = str(path)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture
def _private_context(tmp_path):
    paths = {
        "SCITEX_DIR": tmp_path / "scitex",
        "SCITEX_SCHOLAR_PROJECTS_DIR": tmp_path / "projects",
        "SCITEX_SCHOLAR_LIBRARY_ROOT": tmp_path / "standalone-library",
        "SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE": tmp_path / "mounted-libraries",
    }
    (paths["SCITEX_SCHOLAR_PROJECTS_DIR"] / "Alpha").mkdir(parents=True)
    installed_apps = list(settings.INSTALLED_APPS)
    if "django.contrib.auth" not in installed_apps:
        installed_apps.append("django.contrib.auth")
    with _private_environment(paths), override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
        INSTALLED_APPS=installed_apps,
        SCITEX_PROJECT_PROVIDER="",
        SCITEX_PROJECT_PROVIDER_URL="/api/projects",
        SCITEX_SCHOLAR_CROSSREF_API_URL=None,
    ):
        yield {"paths": paths, "temp_root": tmp_path}


@pytest.fixture(
    params=[
        ("en", "/", "standalone", "SciTeX Scholar"),
        ("ja", "/", "standalone", "SciTeX Scholar"),
        ("en", "/apps/scholar/v2/", "hub", "SciTeX Scholar (hub)"),
        ("ja", "/apps/scholar/v2/", "hub", "SciTeX Scholar (hub)"),
    ],
    ids=["en-root", "ja-root", "en-mounted", "ja-mounted"],
)
def _shell_result(request, _private_context):
    language, path, mode, title = request.param
    http_request = RequestFactory().get(path, HTTP_ACCEPT_LANGUAGE=language)
    with override_settings(SCITEX_APP_MODE=mode), translation.override("en"):
        response = LocaleMiddleware(views.index)(http_request)
    return {
        "response": response,
        "html": response.content.decode(),
        "language": language,
        "prefix": path.rstrip("/"),
        "title": title,
    }


def test_index_shell_context_returns_200(_shell_result):
    # Arrange
    response = _shell_result["response"]
    # Act
    status = response.status_code
    # Assert
    assert status == 200


def test_index_shell_context_tracks_request_language(_shell_result):
    # Arrange
    html = _shell_result["html"]
    # Act
    languages = re.findall(r'<html\b[^>]*\blang="([^"]+)"', html)
    # Assert
    assert languages == [_shell_result["language"]]


def test_index_shell_context_keeps_locale_response_header(_shell_result):
    # Arrange
    response = _shell_result["response"]
    # Act
    language = response.headers["Content-Language"]
    # Assert
    assert language == _shell_result["language"]


def test_index_shell_context_keeps_mount_prefix(_shell_result):
    # Arrange
    html = _shell_result["html"]
    # Act
    prefixes = re.findall(r'<meta name="stx-mount" content="([^"]*)">', html)
    # Assert
    assert prefixes == [_shell_result["prefix"]]


def test_index_shell_context_keeps_configured_mode_title(_shell_result):
    # Arrange
    html = _shell_result["html"]
    # Act
    titles = re.findall(r"<title>([^<]*)</title>", html)
    # Assert
    assert titles == [_shell_result["title"]]


@pytest.mark.parametrize("pane", ["ws-ai-pane", "ws-worktree-pane", "ws-viewer-pane"])
def test_index_shell_context_keeps_explicit_unused_pane(_shell_result, pane):
    # Arrange
    html = _shell_result["html"]
    # Act
    unused = re.findall(
        rf'class="[^"]*\bws-pane-unused\b[^"]*"\s+id="{pane}"', html
    )
    # Assert
    assert len(unused) == 1


def test_index_shell_context_keeps_user_scope(_shell_result):
    # Arrange
    html = _shell_result["html"]
    # Act
    pickers = html.count("data-stx-project-picker")
    # Assert
    assert pickers == 0


def test_index_shell_context_forwards_request_to_csrf_processor(_shell_result):
    # Arrange
    html = _shell_result["html"]
    # Act
    # The explanatory HTML comment also renders {% csrf_token %}; count only
    # the real hidden input in the document, excluding that comment text.
    csrf_inputs = BeautifulSoup(html, "html.parser").find_all(
        "input",
        attrs={
            "name": "csrfmiddlewaretoken",
            "type": "hidden",
            "value": re.compile(r"^[a-zA-Z0-9]{64}$"),
        },
    )
    # Assert
    assert len(csrf_inputs) == 1


@pytest.fixture(
    params=[
        ("/", "bound"),
        ("/apps/scholar/v2/", "bound"),
        ("/", "user"),
        ("/apps/scholar/v2/", "user"),
    ],
    ids=["root-bound", "mounted-bound", "root-user", "mounted-user"],
)
def _private_library_results(request, _private_context):
    from django.contrib.auth import get_user_model

    path, binding = request.param
    prefix = path.rstrip("/")
    results = []
    expected_roots = []
    expected_dois = []
    for username, language in (("alice", "ja"), ("bob", "en")):
        user = get_user_model()(username=username)
        base = _private_context["paths"]["SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE"]
        if binding == "bound":
            base = _private_context["temp_root"] / "bound-libraries"
        root = base / username
        paper = Paper()
        paper.metadata.id.doi = f"10.9/{username}-shell-context"
        paper.metadata.basic.title = f"{username.title()} shell-context paper"
        paper.container.library_id = f"{username.upper()}-CONTEXT"
        PaperIO(paper, base_dir=root / "MASTER").save_metadata()
        index_request = RequestFactory().get(
            path, {"project": "Alpha"}, HTTP_ACCEPT_LANGUAGE=language
        )
        index_request.user = user
        library_request = RequestFactory().get(
            f"{prefix}/api/library", {"project": "Alpha"}
        )
        library_request.user = user
        if binding == "bound":
            index_request.scholar_library_root = root
            library_request.scholar_library_root = root
        with translation.override("en"):
            response = LocaleMiddleware(views.index)(index_request)
        results.append(
            {
                "html": response.content.decode(),
                "root": views._library_root_for(index_request),
                "library": json.loads(views.library_list(library_request).content),
            }
        )
        expected_roots.append(root.resolve())
        expected_dois.append([paper.metadata.id.doi])
    return {
        "results": results,
        "roots": expected_roots,
        "dois": expected_dois,
    }


def test_index_shell_context_preserves_private_request_roots(_private_library_results):
    # Arrange
    results = _private_library_results["results"]
    # Act
    roots = [result["root"] for result in results]
    # Assert
    assert roots == _private_library_results["roots"]


def test_index_shell_context_reports_private_library_roots(_private_library_results):
    # Arrange
    results = _private_library_results["results"]
    # Act
    roots = [result["library"]["library_root"] for result in results]
    # Assert
    assert roots == [str(root) for root in _private_library_results["roots"]]


def test_index_shell_context_keeps_user_libraries_distinct(_private_library_results):
    # Arrange
    results = _private_library_results["results"]
    # Act
    dois = [
        [paper["doi"] for paper in result["library"]["papers"]] for result in results
    ]
    # Assert
    assert dois == _private_library_results["dois"]


def test_index_shell_context_keeps_each_user_request_language(_private_library_results):
    # Arrange
    results = _private_library_results["results"]
    # Act
    languages = [
        re.findall(r'<html\b[^>]*\blang="([^"]+)"', result["html"])
        for result in results
    ]
    # Assert
    assert languages == [["ja"], ["en"]]


def test_scholar_entrypoint_resolves_existing_app_config():
    # Arrange
    entries = importlib.metadata.entry_points(group="scitex.apps")
    # Act
    configs = [entry.load() for entry in entries if entry.name == "scholar"]
    # Assert
    assert configs == [type(apps.get_app_config("scholar_editor"))]


def test_scholar_manifest_keeps_host_route_access_policy():
    # Arrange
    config = apps.get_app_config("scholar_editor")
    # Act
    policy = config.manifest.get("mount_policy") or {}
    # Assert
    assert policy == {}


@pytest.fixture(params=["", "/apps/scholar/v2"], ids=["root", "mounted"])
def _anonymous_public_results(request, _private_context):
    """Call real leaf URL callbacks with anonymous root or mounted requests.

    These portable requests exercise the leaf callbacks; host access middleware
    remains outside this fixture. Health reads configuration and missing-query
    search returns before selecting an engine.
    """
    from django.contrib.auth.models import AnonymousUser

    results = {}
    with override_settings(
        SCITEX_SCHOLAR_CROSSREF_API_URL=None,
        CROSSREF_API_URL=None,
    ):
        for endpoint in ("health", "search"):
            match = resolve(
                f"/api/{endpoint}", urlconf="scitex_scholar._django.urls"
            )
            http_request = RequestFactory().get(f"{request.param}/api/{endpoint}")
            http_request.user = AnonymousUser()
            response = match.func(http_request, *match.args, **match.kwargs)
            results[endpoint] = {
                "response": response,
                "body": json.loads(response.content),
            }
    return results


def test_anonymous_leaf_health_returns_200(_anonymous_public_results):
    # Arrange
    response = _anonymous_public_results["health"]["response"]
    # Act
    status = response.status_code
    # Assert
    assert status == 200


def test_anonymous_leaf_health_reports_configuration_unavailable(
    _anonymous_public_results,
):
    # Arrange
    body = _anonymous_public_results["health"]["body"]
    # Act
    available = body["api_available"]
    # Assert
    assert available is False


def test_anonymous_leaf_search_missing_query_returns_400(_anonymous_public_results):
    # Arrange
    response = _anonymous_public_results["search"]["response"]
    # Act
    status = response.status_code
    # Assert
    assert status == 400


def test_anonymous_leaf_search_reports_required_query(_anonymous_public_results):
    # Arrange
    body = _anonymous_public_results["search"]["body"]
    # Act
    error = body["error"]
    # Assert
    assert error == "q parameter required"


# EOF
