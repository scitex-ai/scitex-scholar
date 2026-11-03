"""Slice 2 (CCT4130 slice-1 UI reflection): search sorter/filter + bulk/pipeline.

Old-direct parity gap, measured 2026-10-17: the leaf backend already covers
search, library save/save-bulk, export/import, enrich, graph, and project
scope, but the Search tab renders results with no sorter, no source filter,
and no way to act on them in bulk -- old-direct had sorters/filters, bulk
actions, and a pipeline pill. This slice reflects the CCT4130 slice-(1)
controls into the leaf Search UI, wired to the EXISTING backend (no new
endpoints): sorter + source filter re-render locally; bulk pills POST to
/api/library/save-bulk; the pipeline pill saves then enriches per paper.
"""

from pathlib import Path

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
SEARCH_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
).read_text()
SEARCH_CSS = (
    Path(views.__file__).parent
    / "static"
    / "scholar"
    / "css"
    / "_partials"
    / "_search.css"
).read_text()


def test_results_card_header_carries_sorter_control():
    """The Results card offers a sort order, not just relevance order."""
    # Arrange
    # Act
    present = 'id="searchSort"' in TEMPLATE
    # Assert
    assert present


def test_results_card_header_carries_source_filter():
    """Results narrow to one corpus; old-direct filtered per source."""
    # Arrange
    # Act
    present = 'id="searchSourceFilter"' in TEMPLATE
    # Assert
    assert present


def test_results_card_header_carries_bulk_bar():
    """Select-all + save-selected + save-and-enrich pills share one bar."""
    # Arrange
    # Act
    bar = (
        'id="searchBulkBar"' in TEMPLATE,
        'id="searchSelectAll"' in TEMPLATE,
        'id="searchSaveSelected"' in TEMPLATE,
        'id="searchEnrichSelected"' in TEMPLATE,
    )
    # Assert
    assert bar == (True, True, True, True)


def test_sorter_options_are_translated_labels():
    """Sorter choices are {% trans %} labels, not English literals (JA rule)."""
    # Arrange
    # Act
    labelled = (
        '{% trans "Relevance" %}' in TEMPLATE,
        '{% trans "Year (newest)" %}' in TEMPLATE,
        '{% trans "Year (oldest)" %}' in TEMPLATE,
        '{% trans "Title (A-Z)" %}' in TEMPLATE,
    )
    # Assert
    assert labelled == (True, True, True, True)


def test_slice2_controls_are_styled():
    """The toolbar/bulk/selection classes live in the search stylesheet."""
    # Arrange
    # Act
    styled = (
        ".search-results-toolbar" in SEARCH_CSS,
        ".search-bulk-bar" in SEARCH_CSS,
        ".search-result__select" in SEARCH_CSS,
    )
    # Assert
    assert styled == (True, True, True)


def test_search_js_re_sorts_on_sorter_change():
    """Changing the sorter re-renders the cached results, no refetch."""
    # Arrange
    # Act
    wired = ('"change"' in SEARCH_JS or "'change'" in SEARCH_JS) and (
        "searchSort" in SEARCH_JS
    )
    # Assert
    assert wired


def test_search_js_bulk_save_posts_to_save_bulk():
    """Save-selected batches through the existing bulk endpoint."""
    # Arrange
    # Act
    wired = "api/library/save-bulk" in SEARCH_JS
    # Assert
    assert wired


def test_search_js_per_result_save_posts_to_library_save():
    """Each result carries its own Save, wired to the single-save endpoint."""
    # Arrange
    # Act -- the closing quote/backtick excludes the save-bulk substring.
    wired = (
        "api/library/save`" in SEARCH_JS
        or 'api/library/save"' in SEARCH_JS
        or "api/library/save'" in SEARCH_JS
    )
    # Assert
    assert wired


def test_search_js_pipeline_pill_enriches_saved_selection():
    """Save-&-enrich chains the existing enrich endpoint per saved paper."""
    # Arrange
    # Act
    wired = "api/library/enrich" in SEARCH_JS
    # Assert
    assert wired


def test_slice2_js_strings_are_translatable():
    """Every new search.js scholarT key exists in the JS i18n dict (JA rule)."""
    # Arrange
    keys = views._js_i18n_dict()
    # Act
    present = (
        "Save" in keys,
        "Saving…" in keys,
        "Saved" in keys,
        "Save failed" in keys,
        "Select results to save." in keys,
        "Saved %(saved)s of %(total)s" in keys,
        "Enriched %(done)s of %(total)s" in keys,
    )
    # Assert
    assert present == (True,) * 7


def test_search_strip_section_mirrors_database_meta():
    # Arrange -- operator 2026-10-22: the Details strip's Databases section
    # mirrors the tier + per-source counts the results header omits.
    # Act
    present = 'getElementById("searchStripSummary")' in SEARCH_JS
    # Assert
    assert present
