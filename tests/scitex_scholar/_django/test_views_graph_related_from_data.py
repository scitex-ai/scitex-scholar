#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch-up: related list derives from the drawn graph (hub parity).

Old related list came from the same NetworkData (no second fetch, no
disagreement with the viz); the leaf refetched /api/graph/related.
CHANGE: derive rows from this.currentData.nodes (seeds first, then
citation count -- hub order), with an empty-state guide when the graph
is empty. VERIFY: pins + no extra fetch.
"""

from __future__ import annotations

from pathlib import Path as _Path

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_GRAPH_JS = (_APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_related_list_comes_from_drawn_graph_data():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- rows derive from currentData.nodes; no second fetch.
    assert (
        "currentData.nodes" in _GRAPH_JS
        and "api/graph/related" not in _GRAPH_JS
    )


def test_empty_graph_explains_itself():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- empty state guides instead of a bare canvas.
    assert "graphEmptyHint" in _GRAPH_JS or "No papers in this graph" in _GRAPH_JS
