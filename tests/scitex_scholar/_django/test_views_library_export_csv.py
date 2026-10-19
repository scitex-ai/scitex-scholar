"""Slice 7 (old-direct unification): CSV library export.

Old-direct parity gap, measured 2026-10-19: hub's export views serve CSV
(Title/Authors/Journal/Year/DOI/PMID/URL/Abstract) while the leaf export
serves bibtex/ris/endnote only -- even though the package formatter
already builds CSV row dicts (``formatting.to_csv_row``). This slice adds
the ``csv`` format to the existing export endpoint (same rows, same auth
scope, ``text/csv`` download) plus the format option in the Library UI.
Library roots bind via ``request.scholar_library_root``.
"""

import csv
import io
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


def _make_paper(root: Path, paper_id: str = "CSV00001") -> None:
    paper_dir = root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.1/csv"},
                    "basic": {
                        "title": "CSV Paper",
                        "authors": ["C. Essvee"],
                        "year": 2023,
                        "abstract": "Comma, separated.",
                    },
                    "publication": {"journal": "J. CSV"},
                }
            }
        )
    )


def _req(root: Path, params: dict):
    req = RequestFactory().get("/api/library/export", params)
    req.scholar_library_root = str(root)
    return req


def test_export_csv_returns_header_and_rows(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_export(_req(tmp_path, {"format": "csv"}))
    # Assert
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    rows = list(csv.DictReader(io.StringIO(resp.content.decode())))
    assert [r["Title"] for r in rows] == ["CSV Paper"]
    assert rows[0]["DOI"] == "10.1/csv" and rows[0]["Year"] == "2023"


def test_export_csv_downloads_as_attachment(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_export(_req(tmp_path, {"format": "csv"}))
    # Assert
    assert "scholar-library.csv" in resp["Content-Disposition"]


def test_export_csv_empty_library_returns_header_only(tmp_path):
    # Arrange
    (tmp_path / "MASTER").mkdir(parents=True, exist_ok=True)
    # Act
    resp = views.library_export(_req(tmp_path, {"format": "csv"}))
    # Assert
    rows = list(csv.DictReader(io.StringIO(resp.content.decode())))
    assert resp.status_code == 200 and rows == []


def test_export_format_error_lists_csv_as_supported(tmp_path):
    # Arrange
    # Act
    resp = views.library_export(_req(tmp_path, {"format": "csljson"}))
    # Assert
    body = json.loads(resp.content)
    assert resp.status_code == 400 and "csv" in body["supported"]


def test_library_export_select_offers_csv():
    # Arrange
    # Act
    present = 'value="csv"' in TEMPLATE
    # Assert
    assert present


def test_library_js_downloads_csv_with_csv_extension():
    # Arrange -- the client-side extension map must name csv, or the
    # download lands as scholar-library.txt.
    # Act
    present = 'csv: "csv"' in LIBRARY_JS
    # Assert
    assert present
