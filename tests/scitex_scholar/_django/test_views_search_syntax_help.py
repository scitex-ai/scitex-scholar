#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U1 (old-direct unification): search syntax-help endpoint + header affordance.

KEEP: hub search behavior unchanged (static JSON docs, mirrors hub
`api_search_syntax_help`). CHANGE: serve via leaf
`GET api/search/syntax-help` + a `?` toggle in the Search header that
fetches and renders it. VERIFY: pins RED-first; zero search behavior
change (no `search` view edits -- this file must not import it).
"""

from __future__ import annotations

import json as _json

from django.test import RequestFactory

from scitex_scholar._django import urls as scholar_urls
from scitex_scholar._django import views


def test_search_syntax_help_answers_200_with_success_status():
    # Arrange
    request = RequestFactory().get("/api/search/syntax-help")
    # Act
    resp = views.search_syntax_help(request)
    # Assert -- one tuple compare (STX-TQ007).
    assert (resp.status_code, _json.loads(resp.content)["status"]) == (200, "success")


def test_search_syntax_help_carries_the_hub_document_shape():
    # Arrange
    request = RequestFactory().get("/api/search/syntax-help")
    # Act
    doc = _json.loads(views.search_syntax_help(request).content)
    # Assert -- the exact top-level keys hub serves (KEEP).
    assert set(doc) == {
        "status", "syntax", "examples", "available_sources", "query_parameters",
    }


def test_search_syntax_help_mirrors_hub_operator_keys():
    # Arrange
    request = RequestFactory().get("/api/search/syntax-help")
    # Act
    doc = _json.loads(views.search_syntax_help(request).content)
    syntax = doc["syntax"]
    # Assert -- operator short/long flags hub documents, one tuple (KEEP).
    assert (
        syntax["title_filter"]["short"],
        syntax["title_filter"]["long"],
        syntax["citations_min"]["example"],
        doc["examples"][0]["query"],
    ) == (
        "-t", "--title", "-cmin 100",
        "neural network -t deep learning -ymin 2020",
    )


def test_search_syntax_help_route_is_flat_and_registered():
    # Arrange -- hub gates each URLPattern.callback with login, so the route
    # must stay a flat path() entry (see test_urls.py).
    # Act
    match = [
        p for p in scholar_urls.urlpatterns if str(p.pattern) == "api/search/syntax-help"
    ]
    # Assert -- exactly one flat entry pointing at the new view.
    assert (len(match), match[0].callback) == (1, views.search_syntax_help)


def test_search_header_carries_syntax_help_affordance():
    # Arrange
    request = RequestFactory().get("/")
    # Act
    body = views.index(request).content.decode()
    # Assert -- the `?` toggle wired to the new endpoint (CHANGE).
    assert 'id="searchSyntaxToggle"' in body and "api/search/syntax-help" in body
