"""CCT4429 (operator via scitex-apps-lead 2026-10-18): the sort-by controls and
the meta around the Search results header look cluttered; simplify to the
essential controls.

Measured 2026-10-18 on develop: the results card stacks THREE strips before
any paper -- (1) the "Results" title row with a 4-part meta
("N papers · cached · <mode> · Local/Online"), (2) a toolbar row with two
visible text labels ("Sort by", "Source") + two selects, (3) a bulk-action
row (select-all + two pills + status). The declutter is presentational, not
functional: every control keeps its id and wiring (slice-2 parity pins stay
green unmodified); the strips merge into one compact row, the two text
labels become select aria-labels, and the meta trims to count + corpus tier
(the tier stays per the local-first readiness policy; mode/cached already
have visible owners in the Advanced block and the request path).
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


def test_sort_and_bulk_share_one_toolbar_row():
    """One compact row holds sorter, source filter, and bulk pills."""
    # Arrange
    toolbar = TEMPLATE.index('class="search-results-toolbar"')
    # Act
    bulk_inside = TEMPLATE.index('id="searchBulkBar"', toolbar)
    body_after = TEMPLATE.index('id="searchResultsContent"')
    # Assert
    assert bulk_inside < body_after


def test_sorter_label_is_an_aria_label_not_visible_text():
    """The sort select names itself accessibly; no "Sort by" text label."""
    # Arrange
    # Act
    visible = '<label class="form-label" for="searchSort"'
    accessible = 'aria-label="{% trans "Sort by" %}"'
    # Assert
    assert visible not in TEMPLATE and accessible in TEMPLATE


def test_source_filter_label_is_an_aria_label_not_visible_text():
    """The source select names itself accessibly; no "Source" text label."""
    # Arrange
    # Act
    visible = '<label class="form-label" for="searchSourceFilter"'
    accessible = 'aria-label="{% trans "Source" %}"'
    # Assert
    assert visible not in TEMPLATE and accessible in TEMPLATE


def test_stats_meta_omits_cache_and_mode_flags():
    """The header meta is count + corpus tier; cached/mode have owners elsewhere."""
    # Arrange
    # Act
    echoed = "metadata.cached" in SEARCH_JS or "metadata.search_mode" in SEARCH_JS
    # Assert
    assert not echoed
