"""Schema test: AccessMetadata must carry pdf_download_{attempted_at,status,error}.

The pipeline uses these fields so a project symlink to a paper whose PDF could
not be fetched is still self-describing. If the schema drifts, downstream
consumers (the UI / bibtex enrichment) silently lose the failure trail.
"""

from scitex_scholar.core.Paper import AccessMetadata


def test_access_metadata_has_pdf_download_fields_m_pdf_download_attempted_at_is_none():
    # Arrange
    # Act
    m = AccessMetadata()
    # Act
    # Assert
    assert m.pdf_download_attempted_at is None


def test_access_metadata_has_pdf_download_fields_m_pdf_download_status_is_none():
    # Arrange
    # Act
    m = AccessMetadata()
    # Act
    # Assert
    assert m.pdf_download_status is None


def test_access_metadata_has_pdf_download_fields_m_pdf_download_error_is_none():
    # Arrange
    # Act
    m = AccessMetadata()
    # Act
    # Assert
    assert m.pdf_download_error is None




def test_access_metadata_accepts_failure_payload():
    # Arrange
    # Act
    m = AccessMetadata(
        pdf_download_attempted_at="2026-04-18T20:00:00+00:00",
        pdf_download_status="download_failed",
        pdf_download_error="Cloudflare challenge blocked",
    )
    # Assert
    assert m.pdf_download_status == "download_failed"


def test_access_metadata_round_trip_json():
    # Arrange
    m = AccessMetadata(pdf_download_status="no_urls")
    d = m.model_dump()
    # Act
    round_trip = AccessMetadata(**d)
    # Assert
    assert round_trip.pdf_download_status == "no_urls"
