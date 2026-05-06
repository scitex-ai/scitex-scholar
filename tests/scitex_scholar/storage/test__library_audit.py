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


def test_clean_library_has_no_issues(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    r = audit(tmp_path)
    assert r.entries_scanned == 2
    assert not r.has_issues
    assert r.n_issues == 0


def test_detects_duplicate_dois(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/SAME")  # case-insensitive dedup
    _write(tmp_path, "CCC", doi="10.2/unique")
    r = audit(tmp_path)
    assert r.has_issues
    assert "10.1/same" in r.duplicate_dois
    ids = {e["paper_id"] for e in r.duplicate_dois["10.1/same"]}
    assert ids == {"AAA", "BBB"}
    assert "10.2/unique" not in r.duplicate_dois


def test_detects_unparseable_json(tmp_path: Path):
    master = tmp_path / "MASTER"
    master.mkdir()
    bad = master / "BAD"
    bad.mkdir()
    (bad / "metadata.json").write_text("{not valid json")
    r = audit(tmp_path)
    assert r.entries_scanned == 1
    assert len(r.unparseable) == 1
    assert r.unparseable[0]["paper_id"] == "BAD"


def test_detects_missing_doi(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi=None)
    r = audit(tmp_path)
    assert r.missing_doi == ["BBB"]
    # Missing DOI isn't counted as corruption (it's common for preprints)
    assert not r.duplicate_dois


def test_detects_missing_pdf(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa", with_pdf=True)
    _write(tmp_path, "BBB", doi="10.2/bbb", with_pdf=False)
    r = audit(tmp_path)
    assert len(r.missing_pdf) == 1
    assert r.missing_pdf[0]["paper_id"] == "BBB"


def test_detects_orphaned_symlinks(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa")
    project = tmp_path / "myproject"
    project.mkdir()
    # orphan: target never existed
    (project / "alice-2024.pdf").symlink_to(tmp_path / "nonexistent.pdf")
    # valid: points at a real MASTER pdf
    (project / "ok-2024.pdf").symlink_to(tmp_path / "MASTER" / "AAA" / "AAA.pdf")
    r = audit(tmp_path)
    assert len(r.orphaned_symlinks) == 1
    assert "alice-2024.pdf" in r.orphaned_symlinks[0]["link"]


def test_missing_master_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        audit(tmp_path)


def test_to_dict_roundtrips_through_json(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    d = r.to_dict()
    dumped = json.dumps(d, default=str)
    assert "duplicate_dois" in dumped
    assert d["n_issues"] >= 2


def test_format_report_includes_duplicates(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/same")
    _write(tmp_path, "BBB", doi="10.1/same")
    r = audit(tmp_path)
    text = format_report(r)
    assert "Duplicate DOIs" in text
    assert "AAA" in text and "BBB" in text


def test_format_report_clean_library(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa")
    text = format_report(audit(tmp_path))
    assert "No issues found" in text
