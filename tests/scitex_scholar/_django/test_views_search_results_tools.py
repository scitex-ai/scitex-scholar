"""Slice 3 (old-direct unification): results-header tools on the Search tab.

Old-direct parity gap, measured 2026-10-19: hub's results header carries
an abstract truncated/full toggle, an Open-URLs-in-tabs button, and an
export-selected-BibTeX button (+ Ctrl+C copy) -- all client-side (hub
generates BibTeX in-browser via Blob download, no backend). The leaf
results toolbar has none of the three. This slice reflects them into the
leaf Search UI over the existing selection set; no new endpoints.
"""

from pathlib import Path

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
SEARCH_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
).read_text()


def test_results_toolbar_carries_abstract_toggle():
    # Arrange -- hub toggles truncated/full abstracts from the header.
    # Act
    present = 'id="searchAbstractToggle"' in TEMPLATE
    # Assert
    assert present


def test_results_toolbar_carries_open_urls_button():
    # Arrange -- hub opens selected papers' URLs in new tabs.
    # Act
    present = 'id="searchOpenUrls"' in TEMPLATE
    # Assert
    assert present


def test_results_toolbar_carries_export_bibtex_button():
    # Arrange -- hub downloads BibTeX for the selected results.
    # Act
    present = 'id="searchExportBibtex"' in TEMPLATE
    # Assert
    assert present


def test_search_js_toggles_abstract_length():
    # Arrange
    # Act
    present = "searchAbstractToggle" in SEARCH_JS
    # Assert
    assert present


def test_search_js_opens_selected_urls():
    # Arrange
    # Act
    present = "searchOpenUrls" in SEARCH_JS
    # Assert
    assert present


def test_search_js_exports_selected_bibtex():
    # Arrange -- hub generates BibTeX client-side (Blob download, no backend).
    # Act
    present = "searchExportBibtex" in SEARCH_JS
    # Assert
    assert present


def test_search_js_copies_bibtex_on_shortcut():
    # Arrange -- hub copies selected BibTeX on Ctrl+C with no text selection.
    # Act
    present = "clipboard" in SEARCH_JS
    # Assert
    assert present
