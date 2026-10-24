"""Operator brief-05 (supersedes the 2026-10-23 seed-only tab): the Graph
tab is seed-from-works plus a Graph Library.

Seeds arrive from the Search/Library tabs (per-row + bulk scholar:build-graph
events, single or multi-seed); the Saved graphs card is back as the Graph
Library with full CRUD (save/list/rename/delete over api/graphs/*). No
typed-DOI Build card returns: no id graphForm/doiInput/graphBuildBtn/topN
anywhere in template or leaf JS.
"""


def test_graph_tab_has_no_build_form():
    # Arrange
    from pathlib import Path

    from scitex_scholar._django import views

    base = Path(views.__file__).parent
    # Act
    template = (base / "templates" / "scholar" / "workspace_content.html").read_text()
    leaf_js = (base / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()
    # Assert
    assert (
        'id="graphForm"' not in template,
        'id="doiInput"' not in template,
        'id="graphBuildBtn"' not in template,
        'id="topN"' not in template,
        'id="graphForm"' not in leaf_js,
    ) == (True,) * 5


def test_graph_tab_has_graph_library_crud_area():
    # Arrange -- brief-05: the Graph Library card (save row + saved list)
    # lives in the Graph tab; the leaf JS drives it against api/graphs/*.
    from pathlib import Path

    from scitex_scholar._django import views

    base = Path(views.__file__).parent
    # Act
    template = (base / "templates" / "scholar" / "workspace_content.html").read_text()
    leaf_js = (base / "static" / "scholar" / "js" / "graph" / "citation-graph.js").read_text()
    present = (
        'id="graphSaveName"' in template,
        'id="graphSaveBtn"' in template,
        'id="graphSavedList"' in template,
        'id="graphLibraryStatus"' in template,
        "api/graphs/save" in leaf_js,
        "api/graphs/list" in leaf_js,
        "api/graphs/rename" in leaf_js,
        "api/graphs/delete" in leaf_js,
        "api/graph/network/multi" in leaf_js,
    )
    # Assert
    assert present == (True,) * 9


def test_graph_tab_seed_list_builds_at_fixed_width():
    # Arrange
    from pathlib import Path

    from scitex_scholar._django import views

    leaf_js = (
        Path(views.__file__).parent
        / "static"
        / "scholar"
        / "js"
        / "graph"
        / "citation-graph.js"
    ).read_text()
    # Act
    seed_only = (
        "DEFAULT_TOP_N" in leaf_js,
        "handleSubmit" not in leaf_js,
    )
    # Assert
    assert seed_only == (True, True)


def test_search_bulk_bar_seeds_graph_from_checked_works():
    # Arrange -- brief-05: the Search bulk bar carries a Graph pill that
    # dispatches checked DOIs (single or multi-seed) to the Graph tab.
    from pathlib import Path

    from scitex_scholar._django import views

    base = Path(views.__file__).parent
    # Act
    template = (base / "templates" / "scholar" / "workspace_content.html").read_text()
    search_js = (base / "static" / "scholar" / "js" / "search.js").read_text()
    # Assert
    assert (
        'id="searchGraphSelected"' in template,
        "scholar:build-graph" in search_js and "dois" in search_js,
    ) == (True, True)


def test_library_rows_seed_graph_from_checked_works():
    # Arrange -- brief-05: Library per-row actions carry a Graph button
    # for DOI rows (same one-shot dispatch as the Search per-row button).
    from pathlib import Path

    from scitex_scholar._django import views

    base = Path(views.__file__).parent
    # Act
    library_js = (base / "static" / "scholar" / "js" / "library.js").read_text()
    # Assert
    assert ("scholar:build-graph" in library_js, 'aria-controls="tab-graph"' in library_js) == (
        True,
        True,
    )
