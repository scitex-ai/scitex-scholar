"""Slice 10 (old-direct unification close-out): library remove + graph rename.

Measured 2026-10-19: hub's details panel removes papers
(api_remove_library_paper) and its graph page renames saved graphs
(api_rename_graph); the leaf ships neither write (the slice-4b details
panel and slice-9 saved list have no such actions). These pins cover the
two endpoints + UI hooks: remove deletes the MASTER/<id>/ tree and its
project filing symlinks (404 unknown, 400 traversal); rename updates the
recipe name (400 empty/overlong, 404 unknown). Library roots bind via
``request.scholar_library_root``.
"""

import json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "library.js"
).read_text()
GRAPH_JS = (
    Path(views.__file__).parent
    / "static"
    / "scholar"
    / "js"
    / "graph"
    / "citation-graph.js"
).read_text()


def _make_paper(root: Path, paper_id: str = "RM000001") -> None:
    paper_dir = root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.1/rm"},
                    "basic": {"title": "Removable", "authors": []},
                }
            }
        )
    )


def _post(path: str, root: Path, data: dict):
    req = RequestFactory().post(
        path, data=json.dumps(data), content_type="application/json"
    )
    req.scholar_library_root = str(root)
    return req


def _get(path: str, root: Path):
    req = RequestFactory().get(path)
    req.scholar_library_root = str(root)
    return req


def test_remove_deletes_the_paper_tree(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_remove(
        _post("/api/library/remove", tmp_path, {"library_id": "RM000001"})
    )
    # Assert
    assert (resp.status_code, (tmp_path / "MASTER" / "RM000001").exists()) == (
        200,
        False,
    )


def test_remove_drops_project_filing_symlinks(tmp_path):
    # Arrange -- file the paper into a project, then remove it.
    _make_paper(tmp_path)
    project_dir = tmp_path / "Alpha"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "RM000001").symlink_to("../MASTER/RM000001")
    # Act
    resp = views.library_remove(
        _post("/api/library/remove", tmp_path, {"library_id": "RM000001"})
    )
    # Assert
    assert (resp.status_code, (project_dir / "RM000001").is_symlink()) == (200, False)


def test_remove_unknown_paper_is_404(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_remove(
        _post("/api/library/remove", tmp_path, {"library_id": "NOPE1234"})
    )
    # Assert
    assert resp.status_code == 404


def test_remove_refuses_path_traversal_ids(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_remove(
        _post("/api/library/remove", tmp_path, {"library_id": "../OUTSIDE"})
    )
    # Assert
    assert resp.status_code == 400


def test_removed_paper_leaves_the_list(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    views.library_remove(
        _post("/api/library/remove", tmp_path, {"library_id": "RM000001"})
    )
    # Act
    body = json.loads(views.library_list(_get("/api/library", tmp_path)).content)
    # Assert
    assert [r["paper_id"] for r in body["papers"]] == []


def test_rename_updates_the_recipe_name(tmp_path):
    # Arrange
    saved = json.loads(
        views.graphs_save(
            _post(
                "/api/graphs/save",
                tmp_path,
                {"name": "Old name", "seed_doi": "10.1/a"},
            )
        ).content
    )
    # Act
    resp = views.graphs_rename(
        _post(
            "/api/graphs/rename",
            tmp_path,
            {"id": saved["id"], "name": "New name"},
        )
    )
    # Assert
    listed = json.loads(views.graphs_list(_get("/api/graphs/list", tmp_path)).content)
    assert (resp.status_code, [g["name"] for g in listed["graphs"]]) == (
        200,
        ["New name"],
    )


def test_rename_rejects_empty_name(tmp_path):
    # Arrange
    saved = json.loads(
        views.graphs_save(
            _post("/api/graphs/save", tmp_path, {"name": "Old", "seed_doi": "10.1/a"})
        ).content
    )
    # Act
    resp = views.graphs_rename(
        _post("/api/graphs/rename", tmp_path, {"id": saved["id"], "name": "  "})
    )
    # Assert
    assert resp.status_code == 400


def test_rename_unknown_id_is_404(tmp_path):
    # Arrange
    # Act
    resp = views.graphs_rename(
        _post("/api/graphs/rename", tmp_path, {"id": "nope", "name": "New"})
    )
    # Assert
    assert resp.status_code == 404


def test_library_details_carries_remove_action():
    # Arrange -- hub's details panel removes the paper from the library.
    # Act
    present = "/api/library/remove" in LIBRARY_JS
    # Assert
    assert present


def test_graph_saved_list_carries_rename_action():
    # Arrange -- hub renames saved graphs from the graph page.
    # Act
    present = "/api/graphs/rename" in GRAPH_JS
    # Assert
    assert present
