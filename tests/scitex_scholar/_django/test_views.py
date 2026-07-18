#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parity tests for the Django port of the Scholar GUI.

Ports the intent of the Flask-era behaviour (no dedicated Flask test file
existed under tests/scitex_scholar/gui/ beyond a smoke-import mirror, so
this is new coverage written directly against the ported views):

  GET /               -> 200, title + favicon link present
  GET /api/health      -> JSON {"status": "ok", "db_available", "db_path"}
  GET /api/graph/network   -> 400 without ?doi=, 503 with no DB configured
  GET /api/graph/related   -> 503 with no DB configured
  GET /api/graph/paper     -> 503 with no DB configured
  GET /api/graph/health    -> 503 with no DB configured

Uses Django's `RequestFactory` directly against the view functions
(bypasses URL routing, same approach as scitex-writer's precedent at
scitex_writer/tests/_django/test_views.py) with a TEST-ONLY settings
bootstrap via conftest.py (bare `django.setup()`, no pytest-django dep).
"""

from __future__ import annotations

import json

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
    assert set(data.keys()) == {"status", "db_available", "db_path"}


def test_graph_network_requires_doi_param():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/network")
    # Act
    resp = views.graph_network(request)
    # Assert
    assert resp.status_code == 400


@override_settings(CROSSREF_DB_PATH=None)
def test_graph_network_returns_503_with_no_db_configured():
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


@override_settings(CROSSREF_DB_PATH=None)
def test_graph_related_returns_503_with_no_db_configured():
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


@override_settings(CROSSREF_DB_PATH=None)
def test_graph_paper_returns_503_with_no_db_configured():
    # Arrange
    rf = RequestFactory()
    request = rf.get("/api/graph/paper?doi=10.1038/s41586-020-2008-3")
    # Act
    resp = views.graph_paper(request)
    # Assert
    assert resp.status_code == 503


@override_settings(CROSSREF_DB_PATH=None)
def test_graph_health_returns_503_with_no_db_configured():
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


# EOF
