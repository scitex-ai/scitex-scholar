"""Slice 5 (old-direct unification): BibTeX import preview.

Old-direct parity gap, measured 2026-10-19: hub's BibTeX flow previews
(upload -> preview/diff -> enrich -> save) while the leaf import saves
sight-unseen. The async job machinery stays hub-owned; the portable piece
is preview-before-save: ``POST /api/library/import`` with ``preview=1``
parses and reports entries (title/authors/year/doi + whether the derived
id already exists) WITHOUT writing anything. The confirm path is the
existing save flow, byte-for-byte unchanged. Library roots bind via
``request.scholar_library_root``.
"""

import json
from pathlib import Path
from urllib.parse import urlencode

from django.test import RequestFactory

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "library.js"
).read_text()

_BIB = """@article{preview_one,
 title={Preview Paper},
 author={A. Uthor and B. Writer},
 journal={J. Test},
 year={2023},
 doi={10.1/preview},
}
"""


def _req(root, data: dict):
    req = RequestFactory().post(
        "/api/library/import",
        data=urlencode(data),
        content_type="application/x-www-form-urlencoded",
    )
    req.scholar_library_root = str(root)
    return req


def test_preview_returns_entries_without_saving(tmp_path):
    # Arrange
    # Act
    resp = views.library_import(
        _req(tmp_path, {"format": "bibtex", "bibtex": _BIB, "preview": "1"})
    )
    # Assert
    body = json.loads(resp.content)
    assert resp.status_code == 200
    assert body["preview"] is True and len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["title"] == "Preview Paper" and entry["doi"] == "10.1/preview"
    assert entry["exists"] is False
    assert not (tmp_path / "MASTER").exists()


def test_preview_flags_entries_already_in_library(tmp_path):
    # Arrange -- import for real first (the unchanged confirm path).
    views.library_import(_req(tmp_path, {"format": "bibtex", "bibtex": _BIB}))
    # Act
    body = json.loads(
        views.library_import(
            _req(tmp_path, {"format": "bibtex", "bibtex": _BIB, "preview": "1"})
        ).content
    )
    # Assert
    assert body["entries"][0]["exists"] is True


def test_preview_rejects_empty_bibtex_without_saving(tmp_path):
    # Arrange
    # Act
    resp = views.library_import(
        _req(tmp_path, {"format": "bibtex", "bibtex": "  ", "preview": "1"})
    )
    # Assert
    assert resp.status_code == 400
    assert not (tmp_path / "MASTER").exists()


def test_confirm_path_still_imports(tmp_path):
    # Arrange
    # Act
    body = json.loads(
        views.library_import(
            _req(tmp_path, {"format": "bibtex", "bibtex": _BIB})
        ).content
    )
    # Assert
    assert body == {"ok": True, "imported": 1}


def test_library_io_carries_preview_panel():
    # Arrange
    # Act
    present = 'id="libraryImportPreview"' in TEMPLATE
    # Assert
    assert present


def test_library_js_previews_before_importing():
    # Arrange -- the file text posts with the preview flag first; the
    # confirm posts the same text without it.
    # Act
    present = "libraryImportPreview" in LIBRARY_JS and "preview:" in LIBRARY_JS
    # Assert
    assert present


def test_library_js_confirms_previewed_import():
    # Arrange
    # Act
    present = "libraryImportConfirm" in LIBRARY_JS
    # Assert
    assert present
