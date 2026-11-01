"""Graph seeds come from Search/Library selection, without a duplicate list.

The old optional graphLibrarySeed helper remains guarded for embedders that
still mount it; its source checks below do not claim the canonical template
renders that list. The native DOM contract now checks compact tab guidance.
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


def test_graph_tab_guides_selection_in_search_and_library_without_repeating_list():
    """Selected works come from their own tabs; Graph owns visualization."""
    # Arrange
    # Act
    picker = (
        'id="graphLibrarySeed"' not in TEMPLATE,
        'data-scholar-seed-tab="search"' in TEMPLATE,
        'data-scholar-seed-tab="library"' in TEMPLATE,
    )
    # Assert
    assert picker == (True, True, True)


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
