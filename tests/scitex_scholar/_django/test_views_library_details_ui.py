"""Slice 4b (old-direct unification): Library details panel + sort control.

Old-direct parity gap, measured 2026-10-19: hub's Library rows expand to a
details panel (reading status, importance stars, tags, personal notes, save)
and the toolbar sorts (newest/oldest/year/title/importance). The leaf rows
show title/meta/DOI/projects/enrich only, with no sort. This slice reflects
the details panel + sort into the leaf Library UI over the slice-4a
annotations backend (no new endpoints): per-row Details toggle, status
radios, star rating, tags editor, notes field, save via /api/library/annotate,
and a client-side sort select. Library remove stays a later sub-slice (no
leaf delete endpoint exists yet).
"""

from pathlib import Path

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "library.js"
).read_text()
CSS_DIR = Path(views.__file__).parent / "static" / "scholar" / "css" / "_partials"


def test_library_filter_row_carries_sort_select():
    # Arrange -- hub sorts the library list from the toolbar.
    # Act
    present = 'id="librarySort"' in TEMPLATE
    # Assert
    assert present


def test_library_row_carries_details_toggle():
    # Arrange -- hub expands a per-paper details panel from each row.
    # Act
    present = "library-details-toggle" in LIBRARY_JS
    # Assert
    assert present


def test_library_details_posts_annotations():
    # Arrange -- the panel saves through the slice-4a update endpoint.
    # Act
    present = "/api/library/annotate" in LIBRARY_JS
    # Assert
    assert present


def test_library_details_renders_status_options():
    # Arrange -- hub offers to_read/reading/read/referenced/favorite.
    # Act
    present = "reading_status" in LIBRARY_JS or "reading-status" in LIBRARY_JS
    # Assert
    assert present


def test_library_details_renders_importance_stars():
    # Arrange -- hub rates importance 1-5 stars.
    # Act
    present = "importance" in LIBRARY_JS
    # Assert
    assert present


def test_library_details_edits_tags_and_notes():
    # Arrange -- hub edits tags + personal notes per paper.
    # Act
    present = ("details-tags" in LIBRARY_JS or "tags" in LIBRARY_JS) and (
        "details-notes" in LIBRARY_JS or "notes" in LIBRARY_JS
    )
    # Assert
    assert present


def test_library_parse_sites_reject_non_json_with_status():
    # Arrange -- operator 2026-10-22: the Library pane showed a raw
    # "Unexpected token '<'" when an endpoint answered HTML instead of JSON.
    # Act
    guarded = "readJson(resp)" in LIBRARY_JS
    raw_gone = "await resp.json();" not in LIBRARY_JS
    # Assert
    assert (guarded, raw_gone) == (True, True)


def test_library_login_redirect_becomes_relogin_prompt():
    # Arrange -- apps-lead probe 2026-10-22: an expired/missing credential
    # is 302'd to the hub login page, so the pane gets HTML where JSON was
    # expected. That shape must prompt re-login, not crash on JSON.parse.
    # Act
    detected = (
        "Session expired. Please log in again." in LIBRARY_JS
        and "/login/i" in LIBRARY_JS
        and "content-type" in LIBRARY_JS
    )
    # Assert
    assert detected


def test_library_strip_section_mirrors_list_counts():
    # Arrange -- operator 2026-10-23: the Details strip's Library section
    # shows the list counts only; the project selection lives in the
    # header picker, so no scope suffix and no indicator mirroring.
    # Act
    counts_only = (
        'getElementById("libraryStripSummary")' in LIBRARY_JS
        and "reflectProjectIndicator()" not in LIBRARY_JS
    )
    # Assert
    assert counts_only


def test_details_export_select_clamps_to_strip_width():
    # Arrange -- operator 2026-10-23 Details-tab style: the Export
    # dropdown overran its narrow strip card (measured live). It must
    # clamp to the card instead of forcing its min-width.
    # Act
    css = (CSS_DIR / "_library.css").read_text()
    # Assert
    assert (".library-io__select" in css, "min-width: 0" in css) == (True, True)


def test_details_advanced_marker_is_ascii_safe():
    # Arrange -- the Details Advanced toggle used U+25B8/25BE markers,
    # which render as tofu boxes on minimal fonts (measured live).
    # Act
    css = (CSS_DIR / "_search.css").read_text()
    # Assert
    assert ('content: "+ "' in css, "\\25B8" not in css) == (True, True)
