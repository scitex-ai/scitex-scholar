#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U4 (old-direct unification): bulk citations in RIS/EndNote over selected.

KEEP: hub S3 selected-papers flow -- format choice over the checked rows,
downloaded file per format (papers.{bib,ris,enw}). CHANGE: RIS/EndNote join
the BibTeX-only client Blob path (leaf formatters, hub tag shapes); no new
endpoint, search behavior unchanged. VERIFY: pins + node syntax check (the
formatters are client code -- the pin is the wiring + hub tag shapes).
"""

from __future__ import annotations

from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

_APP = _Path(_views.__file__).parent
_SEARCH_JS = (_APP / "static" / "scholar" / "js" / "search.js").read_text()


def test_selected_cite_formatters_emit_hub_tag_shapes():
    # Arrange -- hub citation_formats shapes: RIS TY/AU/ER, EndNote %0/%A.
    # Act (no Act step: static text inspection)
    # Assert -- both formatters defined with hub's envelope tags.
    assert (
        "function risEntry(paper)" in _SEARCH_JS
        and "TY  - " in _SEARCH_JS
        and "ER  - " in _SEARCH_JS
        and "function endnoteEntry(paper)" in _SEARCH_JS
        and "%0 " in _SEARCH_JS
        and "%A " in _SEARCH_JS
    )


def test_selected_export_offers_format_choice_over_checked_rows():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static text inspection)
    # Assert -- select with the three formats, button reads it, Blob download
    # keeps the per-format filename.
    assert (
        'id="searchExportFormat"' in body
        and 'value="ris"' in body
        and 'value="endnote"' in body
        and "searchExportFormat" in _SEARCH_JS
        and "scholar-selected-" in _SEARCH_JS
        and '"enw"' in _SEARCH_JS
        and '"ris"' in _SEARCH_JS
    )
