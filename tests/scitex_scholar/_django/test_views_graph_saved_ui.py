"""Slice 9 (old-direct unification): saved-graphs UI on the Graph tab.

Old-direct parity gap, measured 2026-10-19: hub's graph page carries a
tabs bar with save/load/delete over its saved-graph endpoints while the
leaf ships the same backend (graphs_save/list/delete, parity slice 1)
with no UI -- saved graphs are write-only. This slice reflects a saved
graphs card into the leaf Graph tab over the EXISTING endpoints (no new
backend): name + save-current, list with load (rebuilds from the recipe
seed) and delete. The graph JS is a class; the manager owns the wiring.
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


def test_graph_tab_carries_saved_graphs_card():
    # Arrange -- hub saves/loads/deletes graphs from the graph page.
    # Act
    present = 'id="graphSavedBar"' in TEMPLATE
    # Assert
    assert present


def test_graph_saved_bar_carries_name_and_save():
    # Arrange
    # Act
    present = 'id="graphSaveName"' in TEMPLATE and 'id="graphSaveBtn"' in TEMPLATE
    # Assert
    assert present


def test_graph_saved_bar_carries_list():
    # Arrange
    # Act
    present = 'id="graphSavedList"' in TEMPLATE
    # Assert
    assert present


def test_graph_js_saves_current_graph():
    # Arrange -- the manager posts the current seed as a recipe.
    # Act
    present = "/api/graphs/save" in GRAPH_JS
    # Assert
    assert present


def test_graph_js_loads_and_deletes_saved_graphs():
    # Arrange
    # Act
    present = "/api/graphs/list" in GRAPH_JS and "/api/graphs/delete" in GRAPH_JS
    # Assert
    assert present
