"""Render the genuine Details controls without provider requests or stores."""
from pathlib import Path
from bs4 import BeautifulSoup
from django.template import Context, Engine


def _details():
    root = Path(__file__).resolve().parents[4]
    template = (root / "src/scitex_scholar/_django/templates/scholar/workspace_content.html").read_text()
    start = template.index("<div data-search-hint>")
    end = template.index("<!-- Library ops:", start)
    html = Engine(libraries={"i18n": "django.templatetags.i18n"}).from_string(
        "{% load i18n %}" + template[start:end],
    ).render(Context({"api_available": True}))
    return BeautifulSoup(html, "html.parser")


def test_details_follow_reference_group_order_and_native_accessibility():
    # Arrange
    details = _details()
    # Act
    groups = [node["data-search-options"] for node in details.select("details[data-search-options]")]
    # Assert
    assert groups == ["sources", "sorters", "filters"]


def test_details_keep_each_live_control_in_exactly_one_group():
    # Arrange
    details = _details()
    # Act
    actual = {ident: len(details.select(f"#{ident}")) for ident in (
        "searchMode", "searchNoCache", "searchSourcesGrid", "searchSort",
        "searchSourceFilter", "searchYearFrom", "searchYearTo",
        "searchMinCitations", "searchMaxCitations", "searchMinImpact", "searchMaxImpact",
    )}
    # Assert
    assert set(actual.values()) == {1}


def test_sort_buttons_preserve_existing_title_order_and_label_direction():
    # Arrange
    details = _details()
    # Act
    buttons = [(b["data-search-sort"], b["aria-pressed"], bool(b.get("data-label-ascending")))
               for b in details.select("button[data-search-sort]")]
    # Assert
    assert buttons == [(field, "false", True) for field in ("year", "citations", "impact_factor", "title")]


def test_filter_pairs_do_not_nest_duplicate_grids():
    # Arrange
    details = _details()
    # Act
    ranges = [(len(n.select("input")), [i["id"] for i in n.select("input")])
              for n in details.select("fieldset.search-filter-range")]
    # Assert
    assert ranges == [(2, ["searchYearFrom", "searchYearTo"]),
                      (2, ["searchMinCitations", "searchMaxCitations"]),
                      (2, ["searchMinImpact", "searchMaxImpact"])]
