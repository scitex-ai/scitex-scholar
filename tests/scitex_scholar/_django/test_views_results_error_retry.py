"""Error fallback UI (operator UX standard, hub hub-error-fallback-ui-20261016
slice): failed load/API on the Scholar search/library/graph surfaces must
render an explanatory error state WITH retry, never a dead end.

Measured 2026-10-18 on develop+declutter(#231): all three surfaces own an
error box (#searchError / #libraryError / #graphError) with a message and a
Dismiss button -- but no retry affordance. After dismiss the surface sits
empty/hidden; recovery means knowing to resubmit by hand. The leaf has no
reader/PDF surface (no reader/pdf routes or templates), so the standard
covers search/library/graph only.
"""

from pathlib import Path

from django.template.loader import render_to_string
from django.test import RequestFactory

from scitex_scholar._django import views
from scitex_scholar._django.views import _js_i18n_dict

APP = Path(views.__file__).parent
TEMPLATE = (APP / "templates" / "scholar" / "workspace_content.html").read_text()
SEARCH_JS = (APP / "static" / "scholar" / "js" / "search.js").read_text()
LIBRARY_JS = (APP / "static" / "scholar" / "js" / "library.js").read_text()
GRAPH_JS = (APP / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()


def test_search_error_box_carries_a_retry_button():
    """The search failure state offers retry, not just dismiss."""
    # Arrange
    # Act
    button = 'id="searchRetryBtn"'
    label = '{% trans "Retry" %}'
    # Assert
    assert button in TEMPLATE and label in TEMPLATE


def test_library_error_box_carries_a_retry_button():
    """The library load-failure state offers retry, not just dismiss."""
    # Arrange
    # Act
    button = 'id="libraryRetryBtn"'
    label = '{% trans "Retry" %}'
    # Assert
    assert button in TEMPLATE and label in TEMPLATE


def test_graph_error_box_carries_a_retry_button():
    """The graph build-failure state offers retry, not just dismiss."""
    # Arrange
    # Act
    button = 'id="graphRetryBtn"'
    label = '{% trans "Retry" %}'
    # Assert
    assert button in TEMPLATE and label in TEMPLATE


def test_search_retry_re_runs_the_failed_operation():
    """Search retry re-dispatches work; validation errors stay retry-less."""
    # Arrange
    # Act
    wired = "searchRetryBtn" in SEARCH_JS
    resubmits = "requestSubmit" in SEARCH_JS
    validation_bare = 'showError("Enter a search query.")' in SEARCH_JS
    # Assert
    assert wired and resubmits and validation_bare


def test_library_retry_reloads_the_list():
    """Library retry forces a list reload."""
    # Arrange
    # Act
    wired = "libraryRetryBtn" in LIBRARY_JS
    reloads = "loadLibrary(true)" in LIBRARY_JS
    # Assert
    assert wired and reloads


def test_graph_retry_rebuilds_the_last_graph():
    """Graph retry re-runs the failed build with the same seed."""
    # Arrange
    # Act
    wired = "graphRetryBtn" in GRAPH_JS
    remembers = "lastBuild" in GRAPH_JS
    # Assert
    assert wired and remembers


def test_graph_seed_failure_offers_retry():
    """The library-seed picker failure state can be retried in place."""
    # Arrange
    # Act
    marker = "data-seed-retry" in GRAPH_JS
    # Assert
    assert marker


def test_retry_label_is_in_the_js_i18n_dict():
    """scholarT('Retry') resolves client-side in every active language."""
    # Arrange
    # Act
    labels = _js_i18n_dict()
    # Assert
    assert "Retry" in labels


def test_retry_buttons_render_in_english():
    """The live EN page shows Retry on all three error boxes."""
    # Arrange
    request = RequestFactory().get("/")
    # Act
    html = render_to_string("scholar/workspace_content.html", {}, request=request)
    # Assert -- three rendered labels; the ids (...RetryBtn) carry the same
    # substring and the template wraps labels in whitespace, so collapse
    # whitespace first and count the label, not the word.
    flat = "".join(html.split())
    assert "{%trans" not in flat and flat.count(">Retry<") == 3


def test_retry_buttons_render_in_japanese():
    """The live JA page shows 再試行 on all three error boxes."""
    # Arrange
    from django.utils import translation

    request = RequestFactory().get("/")
    # Act
    with translation.override("ja"):
        html = render_to_string("scholar/workspace_content.html", {}, request=request)
    # Assert
    assert html.count("再試行") == 3
