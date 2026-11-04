"""HTTP adapters preserve the native static GET and Django method refusal."""

from __future__ import annotations

import json

import pytest
from django.conf import settings
from django.test import Client, RequestFactory, override_settings

from scitex_scholar._web._api import plugin
from scitex_scholar._web._views import search_syntax_help


@pytest.fixture
def requests():
    if not settings.configured:
        settings.configure(SECRET_KEY="owned-static-help-test", DEFAULT_CHARSET="utf-8")
    return RequestFactory()


def test_public_static_help_response_matches_schema_without_search_execution(requests):
    # Arrange
    request = requests.get(
        "/api/search/syntax-help", {"q": "ignored", "sources": "not-an-engine"}
    )
    # Act
    response = search_syntax_help(request)
    document = json.loads(response.content)
    types = {"string": str, "object": dict, "array": list}
    fields = plugin.routes[0].response.fields
    valid = set(document) == {field.name for field in fields} and all(
        isinstance(document[field.name], types[field.type])
        and (not field.enum or document[field.name] in field.enum)
        for field in fields
    )
    # Assert
    assert (response.status_code, response["Content-Type"], valid) == (
        200,
        "application/json",
        True,
    )


@pytest.mark.parametrize("method", ["get", "post", "head", "delete"])
def test_adapter_preserves_native_response_bytes_and_method_contract(requests, method):
    # Arrange
    from scitex_scholar._django.views import search_syntax_help as native

    request = getattr(requests, method)("/api/search/syntax-help")
    # Act
    actual = search_syntax_help(request)
    expected = native(request)
    # Assert
    assert (actual.status_code, actual.content, dict(actual.headers)) == (
        expected.status_code,
        expected.content,
        dict(expected.headers),
    )


@pytest.mark.parametrize("method", ["post", "head", "delete"])
def test_non_get_remains_native_non_json_405_with_allow_header(requests, method):
    # Arrange
    request = getattr(requests, method)("/api/search/syntax-help")
    # Act
    response = search_syntax_help(request)
    # Assert
    assert (
        response.status_code,
        response["Allow"],
        response["Content-Type"].startswith("text/html"),
    ) == (405, "GET", True)


def test_existing_native_url_serves_the_declared_static_document(requests):
    # Arrange
    expected = search_syntax_help(requests.get("/api/search/syntax-help"))
    # Act
    with override_settings(
        ROOT_URLCONF="scitex_scholar._django.urls",
        ALLOWED_HOSTS=["testserver"],
        MIDDLEWARE=[],
    ):
        actual = Client().get("/api/search/syntax-help")
    # Assert
    assert (actual.status_code, actual.content) == (200, expected.content)
