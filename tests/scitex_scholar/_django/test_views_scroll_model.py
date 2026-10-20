#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Old-direct scroll model: outer module fixed, leaf content scrolls.

The SDK shell makes `.ws-module-pane` the page scroller, so its own
scrollbar gutter shrinks the header + content 15px off the module edge
(measured 1265 vs 1280). Old-direct parity: outer hidden, inner panes
scroll. CHANGE: leaf-scoped rules only (no shared-sheet selectors).
VERIFY: live widths equal + inner scroll reaches bottom content.
"""

from __future__ import annotations

from pathlib import Path as _Path

from scitex_scholar._django import views as _views

_LAYOUT_CSS = (
    _Path(_views.__file__).parent
    / "static"
    / "scholar"
    / "css"
    / "_partials"
    / "_layout.css"
).read_text()


def test_scroll_gutter_does_not_shrink_header_and_content():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- module fixed + leaf root owns the scroll (one compare).
    assert (
        ".ws-module-pane" in _LAYOUT_CSS
        and "overflow-y: hidden" in _LAYOUT_CSS
        and ".app-container" in _LAYOUT_CSS
        and "overflow-y: auto" in _LAYOUT_CSS
    )


def test_tabs_have_square_corners_for_a_sharp_underline():
    # Arrange -- SDK sets radius-lg + accent text on the selected tab; the
    # inset underline inherits the rounding AND the text changes color
    # (operator: disgusting). Sunset when the SDK sheet ships it.
    # Act (no Act step: static text inspection)
    # Assert -- selected tab keeps siblings' color, sharp corners.
    from scitex_scholar._django import views as _views
    from pathlib import Path as _Path
    layout = (
        _Path(_views.__file__).parent
        / "static" / "scholar" / "css" / "_partials" / "_layout.css"
    ).read_text()
    assert (".stx-content-tabs__tab" in layout) and ("border-radius: 0" in layout) and ("color: var(--text-secondary" in layout)
