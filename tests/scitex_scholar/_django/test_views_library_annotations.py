"""Slice 4a (old-direct unification): per-paper library annotations backend.

Old-direct parity gap, measured 2026-10-19: hub's Library details panel
carries reading status, importance stars, tags, and personal notes --
model-backed in hub (UserLibrary/annotations). The leaf library rows carry
none of it. The leaf stores user annotations in a sidecar
(``MASTER/<id>/annotations.json``), never in metadata.json, so enrichment
rewrites can never clobber them (same sidecar precedent as the verify-cites
clew sidecar). These pins cover validation, the update endpoint, and the
list merge. Library roots bind via ``request.scholar_library_root``.
"""

import json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views
from scitex_scholar.storage import _library_annotations as annotations


def _make_paper(root: Path, paper_id: str = "ABC12345") -> Path:
    # Arrange helper: a minimal primary entry the list endpoint can read.
    paper_dir = root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.1/x"},
                    "basic": {"title": "Annotated", "authors": ["A. Uthor"]},
                }
            }
        )
    )
    return paper_dir


def _req(path: str, root: Path, data=None):
    rf = RequestFactory()
    req = (
        rf.post(path, data=json.dumps(data or {}), content_type="application/json")
        if data is not None
        else rf.get(path)
    )
    req.scholar_library_root = str(root)
    return req


def test_validate_annotations_accepts_a_full_doc():
    # Arrange
    # Act
    clean, error = annotations.validate_annotations(
        {
            "reading_status": "reading",
            "importance": 4,
            "tags": ["hippocampus", "review"],
            "notes": "Read the methods.",
        }
    )
    # Assert
    assert (error, clean["reading_status"], clean["importance"]) == (
        None,
        "reading",
        4,
    )


def test_validate_annotations_rejects_unknown_status():
    # Arrange
    # Act
    _, error = annotations.validate_annotations({"reading_status": "skimmed"})
    # Assert
    assert error is not None


def test_validate_annotations_rejects_out_of_range_importance():
    # Arrange
    # Act
    _, error = annotations.validate_annotations({"importance": 6})
    # Assert
    assert error is not None


def test_validate_annotations_rejects_non_list_tags():
    # Arrange
    # Act
    _, error = annotations.validate_annotations({"tags": "hippocampus"})
    # Assert
    assert error is not None


def test_annotate_stores_reading_status_in_the_sidecar(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_annotate(
        _req(
            "/api/library/annotate",
            tmp_path,
            {"library_id": "ABC12345", "reading_status": "read"},
        )
    )
    # Assert
    assert (
        resp.status_code,
        json.loads((tmp_path / "MASTER" / "ABC12345" / "annotations.json").read_text())[
            "reading_status"
        ],
    ) == (200, "read")


def test_annotate_merges_partial_updates(tmp_path):
    # Arrange
    _make_paper(tmp_path)

    def req(data):
        return _req("/api/library/annotate", tmp_path, data)

    # Act
    views.library_annotate(req({"library_id": "ABC12345", "reading_status": "read"}))
    resp = views.library_annotate(req({"library_id": "ABC12345", "importance": 5}))
    # Assert
    body = json.loads(resp.content)
    stored = dict(body["annotations"])
    stored.pop("updated_at", None)
    assert stored == {"reading_status": "read", "importance": 5}


def test_annotate_rejects_bad_status_with_400(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_annotate(
        _req(
            "/api/library/annotate",
            tmp_path,
            {"library_id": "ABC12345", "reading_status": "skimmed"},
        )
    )
    # Assert
    assert resp.status_code == 400


def test_annotate_rejects_unknown_paper_with_404(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_annotate(
        _req(
            "/api/library/annotate",
            tmp_path,
            {"library_id": "NOPE1234", "reading_status": "read"},
        )
    )
    # Assert
    assert resp.status_code == 404


def test_annotate_refuses_path_traversal_ids(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_annotate(
        _req(
            "/api/library/annotate",
            tmp_path,
            {"library_id": "../OUTSIDE", "reading_status": "read"},
        )
    )
    # Assert
    assert resp.status_code == 400


def test_list_merges_annotations_into_rows(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    views.library_annotate(
        _req(
            "/api/library/annotate",
            tmp_path,
            {"library_id": "ABC12345", "reading_status": "reading", "tags": ["x"]},
        )
    )
    # Act
    body = json.loads(views.library_list(_req("/api/library", tmp_path)).content)
    # Assert
    (row,) = [r for r in body["papers"] if r["paper_id"] == "ABC12345"]
    merged = dict(row["annotations"])
    merged.pop("updated_at", None)
    assert merged == {"reading_status": "reading", "tags": ["x"]}


def test_list_rows_without_sidecar_carry_empty_annotations(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    body = json.loads(views.library_list(_req("/api/library", tmp_path)).content)
    # Assert
    (row,) = [r for r in body["papers"] if r["paper_id"] == "ABC12345"]
    assert row["annotations"] == {}


def test_list_degrades_corrupt_sidecar_to_empty(tmp_path):
    # Arrange -- a half-written sidecar must not break the listing.
    paper_dir = _make_paper(tmp_path)
    (paper_dir / "annotations.json").write_text("{not json")
    # Act
    body = json.loads(views.library_list(_req("/api/library", tmp_path)).content)
    # Assert
    (row,) = [r for r in body["papers"] if r["paper_id"] == "ABC12345"]
    assert row["annotations"] == {}
