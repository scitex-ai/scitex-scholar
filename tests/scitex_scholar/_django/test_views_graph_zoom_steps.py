#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U5 (old-direct unification): graph zoom in/out step buttons.

KEEP: hub graph_stage zoomIn/zoomOut position + behavior (step factor
1.4 about the view center, same 0.1-5 clamp as the wheel path); existing
leaf fit/reset stay. CHANGE: wire step-zoom onto the existing renderer
transform (no new renderer). VERIFY: pins + screenshot zoom steps (the
step path is client code -- the pin is the wiring + hub factor).
"""

from __future__ import annotations

from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_GRAPH_JS = (_APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_graph_stage_carries_zoom_step_buttons():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static markup inspection)
    # Assert -- both step buttons exist ahead of the fit control (hub order).
    zoom_out = body.find('id="zoomOutBtn"')
    zoom_in = body.find('id="zoomInBtn"')
    fit = body.find('id="fitViewBtn"')
    assert (zoom_out != -1, zoom_in != -1, zoom_out < zoom_in < fit) == (True, True, True)


def test_zoom_steps_use_hub_factor_on_the_renderer_transform():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- step method zooms about the center with hub's 1.4 factor,
    # clamped to the wheel path's 0.1-5 range, applied to the transform.
    assert (
        "zoomStep(factor)" in _GRAPH_JS
        and "zoomStep(1.4)" in _GRAPH_JS
        and "zoomStep(1 / 1.4)" in _GRAPH_JS
        and "Math.max(0.1, Math.min(5," in _GRAPH_JS
        and "applyTransform(this.transform)" in _GRAPH_JS
    )
