#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U7 (old-direct unification): graph node detail sheet.

KEEP: hub graphNodeSheet dialog role/shape (role=dialog, polite live
region) + the existing canvas picking (click -> selectNode). CHANGE:
the sheet renders from already-loaded graph_data node metadata
(journal + citation count join the existing title/meta/DOI); no new
endpoint. VERIFY: pins click-node-to-sheet with title/meta; Esc/close
returns focus to the invoking node (client code -- the pin is the
wiring).
"""

from __future__ import annotations

from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_GRAPH_JS = (_APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_node_sheet_is_a_polite_dialog():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static markup inspection)
    # Assert -- hub sheet contract: role + live region on the panel shell.
    assert ('id="nodeDetailsPanel"' in body) and ('role="dialog"' in body) and ('aria-live="polite"' in body)


def test_node_sheet_renders_loaded_metadata_with_title_meta_cites():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- the click path feeds the sheet journal + citation count
    # from the node object (no fetch), with title/meta as before.
    assert (
        "showNodeDetails(node)" in _GRAPH_JS
        and "node.journal" in _GRAPH_JS
        and "node.citation_count" in _GRAPH_JS
        and 'scholarT("citations")' in _GRAPH_JS
    )


def test_sheet_escape_and_close_return_focus_to_the_node():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- Esc closes from anywhere; the close path focuses the
    # invoking node element (made focusable at select time).
    assert (
        '"Escape"' in _GRAPH_JS or "'Escape'" in _GRAPH_JS
        and "hideNodeDetails()" in _GRAPH_JS
        and ".focus(" in _GRAPH_JS
        and 'tabindex", "-1"' in _GRAPH_JS
    )


def test_graph_strip_section_mirrors_build_counts():
    # Arrange -- operator 2026-10-22: the Details strip's graph section
    # mirrors the build counts next to the controls.
    # Act
    present = 'getElementById("graphStripSummary")' in _GRAPH_JS
    # Assert
    assert present
