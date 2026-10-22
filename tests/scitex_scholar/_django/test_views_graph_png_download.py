#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U6 (old-direct unification): graph download-PNG.

KEEP: hub downloadPngBtn position in the graph stage header + behavior
(download the current view as citation-graph.png). CHANGE: serialize the
existing SVG to PNG client-side (canvas drawImage, no backend). VERIFY:
pins + node syntax check (client code -- the pin is the wiring + PNG
pipeline shapes). The downloaded file must be a non-blank PNG of the
current view -- asserted structurally here (canvas 2x + toBlob PNG),
visually at dev-verify.
"""

from __future__ import annotations

from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_GRAPH_JS = (_APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_graph_stage_carries_png_download_button():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static markup inspection)
    # Assert -- PNG button sits with the other stage controls.
    assert ('id="downloadPngBtn"' in body) and ('id="downloadSvgBtn"' in body)


def test_png_download_serializes_the_live_svg_to_a_blob():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- SVG serialize -> Image -> canvas 2x -> PNG blob download.
    assert (
        "downloadPng()" in _GRAPH_JS
        and "XMLSerializer" in _GRAPH_JS
        and "drawImage" in _GRAPH_JS
        and "image/png" in _GRAPH_JS
        and "citation-graph.png" in _GRAPH_JS
    )
