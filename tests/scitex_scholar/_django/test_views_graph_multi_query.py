"""Slice 6 (old-direct unification): multi-seed + query graph builds.

Old-direct parity gap, measured 2026-10-19: hub serves
``citation_graph_network_multi`` (?dois=a,b) and
``citation_graph_network_query`` (?q=) while the leaf graph API builds
from one DOI only -- even though the leaf builder already implements
``build_from_dois`` / ``build_from_query``. Hub wires no UI to either
(no callers in hub static/), so this slice is API parity: two thin views
+ routes over the existing builder, same validation/cache/error class as
``graph_network``. Builders are injected fakes (PA-306).
"""

import json

from django.test import RequestFactory

from scitex_scholar._django import views


class _StubGraph:
    def to_dict(self):
        return {"nodes": [], "metadata": {}}


class _RecordingBuilder:
    """Fake builder capturing the multi/query build calls."""

    def __init__(self):
        self.calls = []

    def build_from_dois(self, dois, **kwargs):
        self.calls.append(("dois", list(dois), kwargs))
        return _StubGraph()

    def build_from_query(self, query, **kwargs):
        self.calls.append(("query", query, kwargs))
        return _StubGraph()


def test_graph_network_multi_requires_dois_param():
    # Arrange
    # Act
    resp = views.graph_network_multi(RequestFactory().get("/api/graph/network/multi"))
    # Assert
    assert resp.status_code == 400


def test_graph_network_multi_builds_from_each_doi():
    # Arrange
    builder = _RecordingBuilder()
    request = RequestFactory().get(
        "/api/graph/network/multi?dois=10.1/a,10.1/b&num_related_per_doi=5"
    )
    # Act
    resp = views.graph_network_multi(request, _builder=builder)
    # Assert
    assert (resp.status_code, builder.calls) == (
        200,
        [
            (
                "dois",
                ["10.1/a", "10.1/b"],
                {
                    "num_related_per_doi": 5,
                    "weight_coupling": 2.0,
                    "weight_cocitation": 2.0,
                    "weight_direct": 1.0,
                },
            )
        ],
    )


def test_graph_network_multi_caps_seed_count():
    # Arrange -- hub allows 20; more is a client bug, not a graph.
    builder = _RecordingBuilder()
    dois = ",".join(f"10.1/{i}" for i in range(21))
    request = RequestFactory().get(f"/api/graph/network/multi?dois={dois}")
    # Act
    resp = views.graph_network_multi(request, _builder=builder)
    # Assert
    assert (resp.status_code, builder.calls) == (400, [])


def test_graph_network_multi_rejects_overlong_doi():
    # Arrange
    builder = _RecordingBuilder()
    request = RequestFactory().get(
        "/api/graph/network/multi", {"dois": "10.1000/" + "x" * 100_000}
    )
    # Act
    resp = views.graph_network_multi(request, _builder=builder)
    # Assert
    assert (resp.status_code, builder.calls) == (400, [])


def test_graph_network_query_requires_q_param():
    # Arrange
    # Act
    resp = views.graph_network_query(RequestFactory().get("/api/graph/network/query"))
    # Assert
    assert resp.status_code == 400


def test_graph_network_query_builds_from_query_text():
    # Arrange
    builder = _RecordingBuilder()
    request = RequestFactory().get(
        "/api/graph/network/query?q=hippocampus&num_related_per_doi=5"
    )
    # Act
    resp = views.graph_network_query(request, _builder=builder)
    # Assert
    assert (resp.status_code, builder.calls) == (
        200,
        [
            (
                "query",
                "hippocampus",
                {
                    "num_related_per_doi": 5,
                    "weight_coupling": 2.0,
                    "weight_cocitation": 2.0,
                    "weight_direct": 1.0,
                },
            )
        ],
    )


def test_graph_network_query_marks_uncached_results():
    # Arrange
    builder = _RecordingBuilder()
    request = RequestFactory().get("/api/graph/network/query?q=hippocampus")
    # Act
    resp = views.graph_network_query(request, _builder=builder)
    # Assert
    assert json.loads(resp.content)["metadata"]["cached"] is False


def test_graph_network_multi_is_routed():
    # Arrange -- flat URLPattern entries (hub gates each callback; the
    # urlconf-shape guard in test_urls.py enforces the flatness).
    from scitex_scholar._django import urls as scholar_urls

    # Act
    by_route = {str(p.pattern): p.callback for p in scholar_urls.urlpatterns}
    # Assert
    assert by_route.get("api/graph/network/multi") is views.graph_network_multi


def test_graph_network_query_is_routed():
    # Arrange
    from scitex_scholar._django import urls as scholar_urls

    # Act
    by_route = {str(p.pattern): p.callback for p in scholar_urls.urlpatterns}
    # Assert
    assert by_route.get("api/graph/network/query") is views.graph_network_query
