"""Slice 8 (old-direct unification): single-paper citation endpoint.

Old-direct parity gap, measured 2026-10-19: hub's export ``get_citation``
serves one paper's formatted citation (?paper_id + format) while the leaf
only exports the whole library (or builds BibTeX client-side for search
rows). This slice adds ``GET /api/library/citation`` (?library_id=,
?format= over the library export formats incl. csv): the formatted
citation string for copy-paste, 404 for unknown papers. Library roots bind
via ``request.scholar_library_root``.
"""

import csv
import io
import json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views


def _make_paper(root: Path, paper_id: str = "CIT00001") -> None:
    paper_dir = root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.1/cite"},
                    "basic": {
                        "title": "Cited Paper",
                        "authors": ["C. Itation"],
                        "year": 2022,
                        "abstract": "An abstract.",
                    },
                    "publication": {"journal": "J. Cite"},
                }
            }
        )
    )


def _req(root: Path, params: dict):
    req = RequestFactory().get("/api/library/citation", params)
    req.scholar_library_root = str(root)
    return req


def test_citation_bibtex_carries_title_and_doi(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_citation(
        _req(tmp_path, {"library_id": "CIT00001", "format": "bibtex"})
    )
    # Assert
    body = json.loads(resp.content)
    assert resp.status_code == 200
    assert "Cited Paper" in body["citation"] and "10.1/cite" in body["citation"]
    assert body["format"] == "bibtex"


def test_citation_csv_returns_header_and_row(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_citation(
        _req(tmp_path, {"library_id": "CIT00001", "format": "csv"})
    )
    # Assert
    rows = list(csv.DictReader(io.StringIO(json.loads(resp.content)["citation"])))
    assert [r["Title"] for r in rows] == ["Cited Paper"]


def test_citation_rejects_unsupported_format(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_citation(
        _req(tmp_path, {"library_id": "CIT00001", "format": "csljson"})
    )
    # Assert
    assert resp.status_code == 400


def test_citation_unknown_paper_is_404(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_citation(
        _req(tmp_path, {"library_id": "NOPE1234", "format": "bibtex"})
    )
    # Assert
    assert resp.status_code == 404


def test_citation_refuses_path_traversal_ids(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_citation(
        _req(tmp_path, {"library_id": "../OUTSIDE", "format": "bibtex"})
    )
    # Assert
    assert resp.status_code == 400
