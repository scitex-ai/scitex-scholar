"""Slice 3a (CCT4130 slice-3 graph reflection): How-It-Works + library seed.

Old-direct parity gap, measured 2026-10-17: the leaf Citation Graph tab
takes a typed DOI only and explains nothing, while old-direct pairs the
seed form with (a) a How-It-Works explainer (bibliographic coupling /
co-citation / direct citations) and (b) a seed-from-library picker that
lists library papers carrying a DOI and builds the graph on click
(hub _GraphInputHandler: "Build graph directly from library-selected
DOI"). Backend-availability surfacing is already present (status strip
LEDs + /api/graph/health probe in citation-graph.js), so this slice is
pure reflection over the EXISTING backend: no new endpoints.
"""

from pathlib import Path

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
GRAPH_JS = (
    Path(views.__file__).parent
    / "static"
    / "scholar"
    / "js"
    / "graph"
    / "citation-graph.js"
).read_text()


def test_graph_tab_carries_how_it_works():
    """The graph tab explains the three relatedness signals, translated."""
    # Arrange
    # Act
    panel = (
        '{% trans "How It Works" %}' in TEMPLATE,
        '{% trans "Bibliographic Coupling" %}' in TEMPLATE,
        '{% trans "Co-citation" %}' in TEMPLATE,
        '{% trans "Direct Citations" %}' in TEMPLATE,
    )
    # Assert
    assert panel == (True, True, True, True)


def test_graph_tab_carries_library_seed_picker():
    """The seed form offers library papers with a DOI, not typing only."""
    # Arrange
    # Act
    picker = (
        'id="graphLibrarySeed"' in TEMPLATE,
        '{% trans "Seed from your Library" %}' in TEMPLATE,
    )
    # Assert
    assert picker == (True, True)


def test_graph_js_loads_seed_from_existing_library_endpoint():
    """Seed options come from /api/library (no new endpoint)."""
    # Arrange
    # Act
    wired = "api/library" in GRAPH_JS and "graphLibrarySeed" in GRAPH_JS
    # Assert
    assert wired


def test_graph_js_seed_selection_builds_graph():
    """Clicking a library seed builds the graph for its DOI."""
    # Arrange
    # Act
    builds = "doiInput" in GRAPH_JS and (
        "requestSubmit" in GRAPH_JS or "handleSubmit" in GRAPH_JS
    )
    # Assert
    assert builds


def test_slice3a_js_strings_are_translatable():
    """Every new graph-seed JS string exists in the JS i18n dict (JA rule)."""
    # Arrange
    keys = views._js_i18n_dict()
    # Act
    present = (
        "Seed from your Library" in keys,
        "Loading your library…" in keys,
        "No papers with a DOI in your library yet." in keys,
    )
    # Assert
    assert present == (True,) * 3
