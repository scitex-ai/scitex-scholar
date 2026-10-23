"""Operator 2026-10-23: the Graph tab is seed-only.

The typed-DOI Build Citation Network card and the Saved graphs card are
deleted (no id graphForm/doiInput/graphBuildBtn/topN,
graphSavedBar/graphSaveName/graphSaveBtn/graphSavedList/graphSavedStatus
anywhere in template or leaf JS). The seed list builds directly at the
fixed graph width; CRUD lives on the Library tab's per-row Save keys.
"""


def test_graph_tab_has_no_build_form_or_saved_area():
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
        'id="graphSavedBar"' not in template,
        'id="graphSavedList"' not in template,
        'id="graphForm"' not in leaf_js,
        'id="graphSaveName"' not in leaf_js,
    ) == (True,) * 8


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
