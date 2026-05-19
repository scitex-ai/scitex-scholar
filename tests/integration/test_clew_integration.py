"""Integration tests: scitex-scholar optional scitex-clew provenance hook.

scitex-clew is declared as an OPTIONAL dependency — scholar functionality must
still work when clew is missing, and must populate the clew hash field when
clew is present.
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


def test_missing_clew_does_not_break_save_pdf_paper_container_pdf_sha256_is_none(tmp_path: Path, monkeypatch):
    # Arrange
    import builtins
    real_import = builtins.__import__
    def _fake_import(name, *args, **kwargs):
        if name == "scitex_clew":
            raise ImportError("simulated missing scitex_clew")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO
    src = tmp_path / "src.pdf"
    src.write_bytes(b"fake")
    paper = Paper()
    paper.container.library_id = "CAFEBABE"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    # Act
    io.save_pdf(src)
    # Act
    # Assert
    assert paper.container.pdf_sha256 is None


def test_missing_clew_does_not_break_save_pdf_paper_container_pdf_size_bytes_len_b_fake(tmp_path: Path, monkeypatch):
    # Arrange
    import builtins
    real_import = builtins.__import__
    def _fake_import(name, *args, **kwargs):
        if name == "scitex_clew":
            raise ImportError("simulated missing scitex_clew")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO
    src = tmp_path / "src.pdf"
    src.write_bytes(b"fake")
    paper = Paper()
    paper.container.library_id = "CAFEBABE"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    # Act
    io.save_pdf(src)
    # Act
    # Assert
    assert paper.container.pdf_size_bytes == len(b"fake")


