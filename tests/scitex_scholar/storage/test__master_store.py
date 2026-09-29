#!/usr/bin/env python3
"""Tests for the MASTER primary file store (pure file I/O + derivation).

Store round-trips are deliberately NOT covered here — see
``test__library_index.py`` for why. The best-effort index hook is
exercised only for its failure silence (unreachable store warns and the
files still land).
"""

from __future__ import annotations

import json
from pathlib import Path

from scitex_scholar.storage import _master_store as ms


def test_paper_id_for_doi():
    # Arrange
    doi = "10.1000/xyz:123"
    # Act
    got = ms.paper_id_for(doi, "doi")
    # Assert
    assert got == "doi-10.1000_xyz_123"


def test_paper_id_for_fallback():
    # Arrange
    doi = ""
    # Act
    got = ms.paper_id_for(doi, "")
    # Assert
    assert got == "unknown"


def _add_demo_paper(root: Path):
    return ms.add_paper(
        root,
        "10.1000/demo",
        "doi",
        bibtex_content="@article{demo, title={Demo}}",
        metadata={
            "basic": {"title": "Demo Paper", "year": 2024},
            "publication": {"journal": "J Demo"},
        },
    )


def test_add_paper_bibtex_under_master(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    result = _add_demo_paper(root)
    # Assert
    assert str(result["bibtex"]).startswith("MASTER/")


def test_add_paper_writes_no_pdf_by_default(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    result = _add_demo_paper(root)
    # Assert
    assert "pdf" not in result


def test_add_paper_bib_file_exists(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    _add_demo_paper(root)
    entry = root / "MASTER" / "doi-10.1000_demo"
    # Assert
    assert (entry / "doi-10.1000_demo.bib").exists()


def test_add_paper_metadata_title(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    _add_demo_paper(root)
    meta = json.loads(
        (root / "MASTER" / "doi-10.1000_demo" / "metadata.json").read_text()
    )["metadata"]
    # Assert
    assert meta["basic"]["title"] == "Demo Paper"


def test_add_paper_metadata_doi(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    _add_demo_paper(root)
    meta = json.loads(
        (root / "MASTER" / "doi-10.1000_demo" / "metadata.json").read_text()
    )["metadata"]
    # Assert
    assert meta["id"]["doi"] == "10.1000/demo"


def test_add_paper_flat_metadata_title(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    result = ms.add_paper(
        root,
        "10.1000/flat",
        "doi",
        bibtex_content="@article{flat, title={Flat}}",
        metadata={"title": "Flat Paper", "year": 2023},
    )
    meta = json.loads(
        (root / result["bibtex"]).parent.joinpath("metadata.json").read_text()
    )["metadata"]
    # Assert
    assert meta["basic"]["title"] == "Flat Paper"


def test_add_paper_flat_metadata_year(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    result = ms.add_paper(
        root,
        "10.1000/flat",
        "doi",
        bibtex_content="@article{flat, title={Flat}}",
        metadata={"title": "Flat Paper", "year": 2023},
    )
    meta = json.loads(
        (root / result["bibtex"]).parent.joinpath("metadata.json").read_text()
    )["metadata"]
    # Assert
    assert meta["basic"]["year"] == 2023


def test_add_paper_nested_wins_over_flat(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    ms.add_paper(
        root,
        "10.1000/both",
        "doi",
        metadata={"title": "Flat", "basic": {"title": "Nested"}},
    )
    meta = json.loads(
        (root / "MASTER" / "doi-10.1000_both" / "metadata.json").read_text()
    )["metadata"]
    # Assert
    assert meta["basic"]["title"] == "Nested"


def test_get_paper_path_missing_returns_none(tmp_path):
    # Arrange
    root = tmp_path
    # Act
    found = ms.get_paper_path(root, "10.1000/x", "doi", "bib")
    # Assert
    assert found is None


def test_get_paper_path_roundtrip(tmp_path):
    # Arrange
    root = tmp_path
    ms.add_paper(
        root, "10.1000/x", "doi", bibtex_content="@article{x, title={X}}"
    )
    # Act
    found = ms.get_paper_path(root, "10.1000/x", "doi", "bib")
    # Assert
    assert found is not None and found.name == "doi-10.1000_x.bib"


def test_list_papers_excludes_master_without_pdf(tmp_path):
    # Arrange
    root = tmp_path
    ms.add_paper(root, "10.1000/a", "doi")
    legacy = root / "papers" / "doi"
    legacy.mkdir(parents=True)
    (legacy / "10.9999_b.pdf").write_text("pdf")
    # Act
    rows = ms.list_papers(root)
    kinds = {(r["identifier"], r["id_type"]) for r in rows}
    # Assert
    assert ("doi-10.1000_a", "master") not in kinds  # no PDF written


def test_list_papers_includes_legacy_pdf(tmp_path):
    # Arrange
    root = tmp_path
    ms.add_paper(root, "10.1000/a", "doi")
    legacy = root / "papers" / "doi"
    legacy.mkdir(parents=True)
    (legacy / "10.9999_b.pdf").write_text("pdf")
    # Act
    rows = ms.list_papers(root)
    kinds = {(r["identifier"], r["id_type"]) for r in rows}
    # Assert
    assert ("10.9999_b", "doi") in kinds


def test_index_hook_failure_is_silent(tmp_path):
    # Arrange — swap the store opener explicitly (no mocks); restore in
    # finally so a failure here cannot leak into other tests.
    import scitex_scholar.storage._library_index as idx

    original = idx._open_store

    def _down():
        raise ConnectionError("down")

    idx._open_store = _down
    try:
        # Act
        ms.add_paper(tmp_path, "10.1000/q", "doi")
        # Assert — files still land despite the unreachable store.
        assert (tmp_path / "MASTER" / "doi-10.1000_q").is_dir()
    finally:
        idx._open_store = original


# EOF
