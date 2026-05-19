#!/usr/bin/env python3
"""Tests for the read-only library auditor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_scholar.storage._library_audit import audit, format_report


def _write(
    root: Path,
    paper_id: str,
    *,
    doi: str | None = None,
    with_pdf: bool = True,
    raw_json: str | None = None,
) -> None:
    entry = root / "MASTER" / paper_id
    entry.mkdir(parents=True)
    if raw_json is not None:
        (entry / "metadata.json").write_text(raw_json)
    else:
        md = {
            "metadata": {
                "id": {"doi": doi},
                "basic": {"title": f"Paper {paper_id}"},
                "path": {"pdfs": [f"{paper_id}.pdf"]} if with_pdf else {},
            }
        }
        (entry / "metadata.json").write_text(json.dumps(md))
    if with_pdf:
        (entry / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4 stub")


def test_clean_library_has_no_issues_r_entries_scanned_equals_n_2(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.entries_scanned == 2


def test_clean_library_has_no_issues_not_r_has_issues(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert not r.has_issues


def test_clean_library_has_no_issues_r_n_issues_equals_n_0(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.n_issues == 0




def test_detects_duplicate_dois_r_has_issues(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/SAME")  # case-insensitive dedup
    _write(tmp_path, "CCC", doi="10.2/unique")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.has_issues


def test_detects_duplicate_dois_n_10_1_same_in_r_duplicate_dois(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/SAME")  # case-insensitive dedup
    _write(tmp_path, "CCC", doi="10.2/unique")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert "10.1/same" in r.duplicate_dois


def test_detects_duplicate_dois_ids_equals_aaa_bbb(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/SAME")  # case-insensitive dedup
    _write(tmp_path, "CCC", doi="10.2/unique")
    r = audit(tmp_path)
    # Act
    ids = {e["paper_id"] for e in r.duplicate_dois["10.1/same"]}
    # Act
    # Assert
    assert ids == {"AAA", "BBB"}


def test_detects_duplicate_dois_n_10_2_unique_not_in_r_duplicate_dois(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/SAME")  # case-insensitive dedup
    _write(tmp_path, "CCC", doi="10.2/unique")
    r = audit(tmp_path)
    # Act
    ids = {e["paper_id"] for e in r.duplicate_dois["10.1/same"]}
    # Act
    # Assert
    assert "10.2/unique" not in r.duplicate_dois




def test_detects_unparseable_json_r_entries_scanned_equals_n_1(tmp_path: Path):
    # Arrange
    master = tmp_path / "MASTER"
    master.mkdir()
    bad = master / "BAD"
    bad.mkdir()
    (bad / "metadata.json").write_text("{not valid json")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.entries_scanned == 1


def test_detects_unparseable_json_len_r_unparseable_is_1(tmp_path: Path):
    # Arrange
    master = tmp_path / "MASTER"
    master.mkdir()
    bad = master / "BAD"
    bad.mkdir()
    (bad / "metadata.json").write_text("{not valid json")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert len(r.unparseable) == 1


def test_detects_unparseable_json_r_unparseable_0_paper_id_bad(tmp_path: Path):
    # Arrange
    master = tmp_path / "MASTER"
    master.mkdir()
    bad = master / "BAD"
    bad.mkdir()
    (bad / "metadata.json").write_text("{not valid json")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.unparseable[0]["paper_id"] == "BAD"




def test_detects_missing_doi_r_missing_doi_equals_bbb(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi=None)
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.missing_doi == ["BBB"]


def test_detects_missing_doi_not_r_duplicate_dois(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi=None)
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert not r.duplicate_dois




def test_detects_missing_pdf_len_r_missing_pdf_is_1(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa", with_pdf=True)
    _write(tmp_path, "BBB", doi="10.2/bbb", with_pdf=False)
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert len(r.missing_pdf) == 1


def test_detects_missing_pdf_r_missing_pdf_0_paper_id_bbb(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa", with_pdf=True)
    _write(tmp_path, "BBB", doi="10.2/bbb", with_pdf=False)
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert r.missing_pdf[0]["paper_id"] == "BBB"




def test_detects_orphaned_symlinks_len_r_orphaned_symlinks_is_1(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    project = tmp_path / "myproject"
    project.mkdir()
    # orphan: target never existed
    (project / "alice-2024.pdf").symlink_to(tmp_path / "nonexistent.pdf")
    # valid: points at a real MASTER pdf
    (project / "ok-2024.pdf").symlink_to(tmp_path / "MASTER" / "AAA" / "AAA.pdf")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert len(r.orphaned_symlinks) == 1


def test_detects_orphaned_symlinks_alice_2024_pdf_in_r_orphaned_symlinks_0_link(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    project = tmp_path / "myproject"
    project.mkdir()
    # orphan: target never existed
    (project / "alice-2024.pdf").symlink_to(tmp_path / "nonexistent.pdf")
    # valid: points at a real MASTER pdf
    (project / "ok-2024.pdf").symlink_to(tmp_path / "MASTER" / "AAA" / "AAA.pdf")
    # Act
    r = audit(tmp_path)
    # Act
    # Assert
    assert "alice-2024.pdf" in r.orphaned_symlinks[0]["link"]




def test_missing_master_dir_raises(tmp_path: Path):
    # Arrange
    # Act
    # Assert
    with pytest.raises(FileNotFoundError):
        audit(tmp_path)


def test_to_dict_roundtrips_through_json_duplicate_dois_in_dumped(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    d = r.to_dict()
    # Act
    dumped = json.dumps(d, default=str)
    # Act
    # Assert
    assert "duplicate_dois" in dumped


def test_to_dict_roundtrips_through_json_d_n_issues_2(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    d = r.to_dict()
    # Act
    dumped = json.dumps(d, default=str)
    # Act
    # Assert
    assert d["n_issues"] >= 2




def test_format_report_includes_duplicates_duplicate_dois_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    # Act
    text = format_report(r)
    # Act
    # Assert
    assert "Duplicate DOIs" in text


def test_format_report_includes_duplicates_aaa_in_text_and_bbb_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    # Act
    text = format_report(r)
    # Act
    # Assert
    assert "AAA" in text and "BBB" in text




def test_format_report_clean_library(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    # Act
    text = format_report(audit(tmp_path))
    # Assert
    assert "No issues found" in text
