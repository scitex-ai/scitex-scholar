"""Slice 3a (CCT4130 slice-3 graph reflection): library seed.

Old-direct parity gap, measured 2026-10-17: the leaf Citation Graph tab
takes a typed DOI only, while old-direct pairs the seed form with a
seed-from-library picker that lists library papers carrying a DOI and
builds the graph on click (hub _GraphInputHandler: "Build graph
directly from library-selected DOI"). Backend-availability surfacing is
already present (status strip LEDs + /api/graph/health probe in
citation-graph.js), so this slice is pure reflection over the EXISTING
backend: no new endpoints.

NOTE (operator 2026-10-22, screenshot loop): the How-It-Works explainer
that rode along with this slice is REMOVED -- static explainer copy the
operator judged clutter. Its pin
(test_graph_tab_carries_how_it_works) is deleted, not skipped; the
seed picker below is this file's surviving contract.
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
    """Clicking a library seed builds the graph directly (no form)."""
    # Arrange
    # Act
    builds = "DEFAULT_TOP_N" in GRAPH_JS and "handleSubmit" not in GRAPH_JS
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


def test_graph_seed_items_build_directly_at_fixed_width():
    # Arrange -- operator 2026-10-23 (seed-only tab): no DOI form, so no
    # disabled-until-typed arming; clicking a seed builds directly.
    # Act
    direct = "buildGraph(doi, CitationGraphManager.DEFAULT_TOP_N)" in GRAPH_JS
    # Assert
    assert direct


def test_graph_tab_announces_activation_for_lazy_consumers():
    # Arrange -- operator 2026-10-22 (screenshot loop): the health probe
    # must fire on ANY tab-open path (click/swipe/arrow/prefill), so the
    # single producer (app.js activateTab) announces and the graph module
    # listens -- no per-modality click clones that miss paths.
    # Act
    announced = "scholar:tab-activated" in Path(
        views.__file__
    ).parent.joinpath("static", "scholar", "js", "app.js").read_text()
    consumed = "scholar:tab-activated" in GRAPH_JS
    # Assert
    assert (announced, consumed) == (True, True)
