"""Slice 11 (old-direct unification): open-access PDF download.

Old-direct parity gap, measured 2026-10-19: hub's results header carries
``downloadSelectedPdfs`` (OA-only bulk through its download manager) and
its library cards offer PDF actions, while no leaf endpoint or UI
downloads anything -- search rows carry ``pdf_url``/``is_open_access``
but they are display-only. This slice adds ``POST
/api/library/download-pdfs`` ({library_ids: [...], at most 10}: OA-only
fetch via ScholarPDFDownloader into the paper dir through PaperIO, with
per-item results) plus the two UI surfaces: a Download-PDF button in the
Library details panel and a PDFs bulk pill on Search (saves selected via
save-bulk, then downloads). The downloader is an injected fake (PA-306).
Library roots bind via ``request.scholar_library_root``.
"""

import json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views

TEMPLATE = (
    Path(views.__file__).parent / "templates" / "scholar" / "workspace_content.html"
).read_text()
SEARCH_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "library.js"
).read_text()


def _make_paper(root: Path, paper_id: str = "PDF00001", oa_url=None) -> None:
    access = {"is_open_access": bool(oa_url)}
    if oa_url:
        access["oa_url"] = oa_url
    paper_dir = root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.1/pdf"},
                    "basic": {"title": "PDF Paper", "authors": []},
                    "access": access,
                }
            }
        )
    )


def _post(root: Path, data: dict):
    req = RequestFactory().post(
        "/api/library/download-pdfs",
        data=json.dumps(data),
        content_type="application/json",
    )
    req.scholar_library_root = str(root)
    return req


class _StubFetch:
    """Fake OA fetch: records URLs, pretends every fetch works."""

    def __init__(self):
        self.calls = []

    async def __call__(self, oa_url, output_path, metadata=None):
        self.calls.append(oa_url)
        Path(output_path).write_bytes(b"%PDF-1.4 fake")
        return Path(output_path)


def test_download_pdfs_fetches_oa_papers(tmp_path):
    # Arrange
    _make_paper(tmp_path, oa_url="https://example.org/a.pdf")
    # Act
    resp = views.library_download_pdfs(
        _post(tmp_path, {"library_ids": ["PDF00001"]}),
        _fetch=_StubFetch(),
    )
    # Assert
    body = json.loads(resp.content)
    assert resp.status_code == 200
    assert body["downloaded"] == [{"library_id": "PDF00001"}]
    assert body["failed"] == []
    assert list((tmp_path / "MASTER" / "PDF00001").glob("*.pdf")) != []


def test_download_pdfs_skips_papers_without_oa_url(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_download_pdfs(
        _post(tmp_path, {"library_ids": ["PDF00001"]}),
        _fetch=_StubFetch(),
    )
    # Assert
    body = json.loads(resp.content)
    assert [(f["index"], f["error"]) for f in body["failed"]] == [
        (0, "No open-access PDF available")
    ]
    assert body["downloaded"] == []


def test_download_pdfs_caps_batch_size(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_download_pdfs(
        _post(tmp_path, {"library_ids": [f"P{i:06d}" for i in range(11)]}),
        _fetch=_StubFetch(),
    )
    # Assert
    assert resp.status_code == 400


def test_download_pdfs_unknown_paper_is_reported_not_raised(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_download_pdfs(
        _post(tmp_path, {"library_ids": ["NOPE1234"]}),
        _fetch=_StubFetch(),
    )
    # Assert
    body = json.loads(resp.content)
    assert resp.status_code == 200
    assert [(f["index"], f["error"]) for f in body["failed"]] == [(0, "Paper not found")]


def test_download_pdfs_refuses_path_traversal_ids(tmp_path):
    # Arrange
    _make_paper(tmp_path)
    # Act
    resp = views.library_download_pdfs(
        _post(tmp_path, {"library_ids": ["../OUTSIDE"]}),
        _fetch=_StubFetch(),
    )
    # Assert
    assert resp.status_code == 400


def test_library_details_carries_download_pdf_action():
    # Arrange
    # Act
    present = "/api/library/download-pdfs" in LIBRARY_JS
    # Assert
    assert present


def test_search_bulk_bar_carries_pdfs_pill():
    # Arrange -- hub's header downloads PDFs for the checked rows.
    # Act
    present = "searchDownloadPdfs" in TEMPLATE and "searchDownloadPdfs" in SEARCH_JS
    # Assert
    assert present
