"""Integration tests: scitex-scholar optional scitex-clew provenance hook.

scitex-clew is declared as an OPTIONAL dependency — scholar functionality must
still work when clew is missing, and must populate the clew hash field when
clew is present.

The "clew is missing" path used to be tested by patching ``builtins.__import__``
via ``monkeypatch`` — a mock-shaped pattern that the PA-306 / STX-NM rules
forbid. ``PaperIO.save_pdf`` now exposes a ``clew_module`` keyword (default
``_CLEW_UNSET`` triggers the real lazy import; pass ``None`` to simulate
"clew not installed"; pass a real scitex_clew-shaped module to exercise the
hashing path). The tests below use that injection seam — no mocks involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("scitex_clew")


def test_hash_file_matches_clew_direct(tmp_path: Path):
    """PaperIO.save_pdf must populate container.pdf_sha256 via clew.hash_file."""
    # Arrange
    import scitex_clew as clew

    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO

    # Minimal PDF-like payload — clew.hash_file only reads bytes.
    src = tmp_path / "src.pdf"
    src.write_bytes(b"%PDF-1.4 fake content for hash test\n")
    expected = clew.hash_file(src)

    paper = Paper()
    paper.container.library_id = "DEADBEEF"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    # Act
    io.save_pdf(src)
    # Assert
    assert paper.container.pdf_sha256 == expected


def test_missing_clew_does_not_break_save_pdf_pdf_sha256_is_none(tmp_path: Path):
    # Arrange
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO

    src = tmp_path / "src.pdf"
    src.write_bytes(b"fake")
    paper = Paper()
    paper.container.library_id = "CAFEBABE"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    # Act
    io.save_pdf(src, clew_module=None)
    # Assert
    assert paper.container.pdf_sha256 is None


def test_missing_clew_does_not_break_save_pdf_pdf_size_bytes_recorded(tmp_path: Path):
    # Arrange
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO

    src = tmp_path / "src.pdf"
    src.write_bytes(b"fake")
    paper = Paper()
    paper.container.library_id = "CAFEBABE"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    # Act
    io.save_pdf(src, clew_module=None)
    # Assert
    assert paper.container.pdf_size_bytes == len(b"fake")
