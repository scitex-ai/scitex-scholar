#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch-up: node sheet actions (old-direct parity).

Old graphNodeSheet offered Add-to-library + Explore-from-here; the leaf
sheet had neither. CHANGE: both actions, wired to EXISTING endpoints
(library_save POST; buildGraph rebuild) -- no new backend. VERIFY: pins.
"""

from __future__ import annotations

from pathlib import Path as _Path

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_GRAPH_JS = (_APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_node_sheet_adds_to_library_through_existing_save():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- add action posts node fields to the leaf save endpoint,
    # reusing the Saved/Save-failed strings.
    assert (
        'data-act="add"' in _GRAPH_JS
        and "api/library/save" in _GRAPH_JS
        and "addToLibrary" in _GRAPH_JS
    )


def test_node_sheet_explores_from_non_seed_nodes():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- explore action rebuilds the graph from the tapped DOI.
    assert (
        'data-act="explore"' in _GRAPH_JS
        and "exploreFromHere" in _GRAPH_JS
    )
