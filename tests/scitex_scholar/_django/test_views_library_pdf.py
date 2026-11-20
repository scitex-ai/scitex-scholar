"""Saved PDF delivery uses the library root already resolved for the request."""

from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from scitex_scholar._django.views import library_pdf

PDF = b"%PDF-1.7\nPDF fixture"


def _record(root: Path):
    paper = root / "MASTER" / "PDF00001"
    paper.mkdir(parents=True)
    (paper / "metadata.json").write_text("{}")
    return paper


def _request(root: Path, library_id="PDF00001"):
    request = RequestFactory().get(
        "/apps/scholar/api/library/pdf", {"library_id": library_id}
    )
    request.scholar_library_root = root
    return request


def test_saved_pdf_streams_from_scoped_library(tmp_path):
    # Arrange
    own = tmp_path / "own"
    other = tmp_path / "other"
    (_record(own) / "paper.pdf").write_bytes(PDF)
    (_record(other) / "paper.pdf").write_bytes(b"%PDF-1.7\nOther library")
    # Act
    response = library_pdf(_request(own))
    try:
        observed = (
            response.status_code,
            response.headers["Content-Type"],
            response.headers["Cache-Control"],
            b"".join(response.streaming_content),
        )
    finally:
        response.close()
    # Assert
    assert observed == (200, "application/pdf", "private, no-store", PDF)


def test_mounted_pdf_requires_authenticated_library_scope():
    # Arrange
    request = RequestFactory().get(
        "/apps/scholar/api/library/pdf", {"library_id": "PDF00001"}
    )
    # Act
    # Assert
    with pytest.raises(PermissionDenied):
        library_pdf(request)


def test_pdf_request_rejects_invalid_library_id(tmp_path):
    # Arrange
    request = _request(tmp_path, "../other")
    # Act
    response = library_pdf(request)
    # Assert
    assert response.status_code == 400


def test_pdf_ignores_nonlocal_and_incomplete_files(tmp_path):
    # Arrange
    own = tmp_path / "own"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(PDF)
    record = _record(own)
    (record / "saved.pdf").symlink_to(outside)
    (record / "download-tmp.pdf").write_bytes(PDF)
    (record / "supple-appendix.pdf").write_bytes(PDF)
    (record / "directory.pdf").mkdir()
    # Act
    response = library_pdf(_request(own))
    # Assert
    assert response.status_code == 404


def test_pdf_refuses_a_linked_paper_directory(tmp_path):
    # Arrange
    own = tmp_path / "own"
    (own / "MASTER").mkdir(parents=True)
    other = _record(tmp_path / "other")
    (other / "paper.pdf").write_bytes(PDF)
    (own / "MASTER" / "PDF00001").symlink_to(other, target_is_directory=True)
    # Act
    response = library_pdf(_request(own))
    # Assert
    assert response.status_code == 404
