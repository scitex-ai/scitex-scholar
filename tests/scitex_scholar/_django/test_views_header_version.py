#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Header version display (operator 2026-10-20: subdued, not removed).

The header version pill reads as loud UI chrome. CHANGE: shrink + mute
it via one leaf-scoped rule (monotone, reversible); the version stays
in the DOM (title tooltip intact) so bug reports keep it. Alternatives
considered: hide entirely (loses debuggability), relocate to Details
(two surfaces). VERIFY: pins.
"""

from __future__ import annotations

from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_LAYOUT_CSS = (_APP / "static" / "scholar" / "css" / "_partials" / "_layout.css").read_text()


def test_header_keeps_version_in_dom():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static markup inspection)
    # Assert -- debuggability kept: version span + package tooltip survive.
    assert ('class="stx-app-header__version"' in body) and ('title="scitex-scholar package serving this page"' in body)


def test_header_version_is_subdued_by_leaf_rule():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- one leaf-scoped rule shrinks + mutes the shared pill.
    assert (
        '.scholar-app-header .stx-app-header__version' in _LAYOUT_CSS
        and 'font-size: 10px' in _LAYOUT_CSS
    )
