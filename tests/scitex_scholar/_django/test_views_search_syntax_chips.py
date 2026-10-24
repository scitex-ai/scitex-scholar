#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch-up: click-to-insert syntax chips (old-direct parity).

Old search help had clickable operator chips that inserted the flag
into the query box. CHANGE: flag terms + example queries insert/fill
the query input on click. VERIFY: pins.
"""

from __future__ import annotations

from pathlib import Path as _Path

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_SEARCH_JS = (_APP / "static" / "scholar" / "js" / "search.js").read_text()


def test_syntax_chips_insert_into_query_box():
    # Arrange (no Arrange step: static text inspection)
    # Act (no Act step: static text inspection)
    # Assert -- flag click inserts at cursor; example click fills input.
    assert (
        "insertSyntaxToken" in _SEARCH_JS
        and "setSelectionRange" in _SEARCH_JS
        and "searchInput" in _SEARCH_JS
    )
