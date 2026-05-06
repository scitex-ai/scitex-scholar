#!/usr/bin/env python3
"""Tests for the library SQLite index."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scitex_scholar.storage import _library_index as idx


def _write_entry(
    root: Path,
    paper_id: str,
    doi: str | None = None,
    arxiv_id: str | None = None,
    pmid: str | None = None,
    title: str = "t",
    year: int | None = 2024,
    journal: str = "J",
    is_oa: bool = False,
    authors: list[str] | None = None,
    abstract: str | None = None,
    citation_count: int | None = None,
) -> None:
    entry = root / "MASTER" / paper_id
    entry.mkdir(parents=True)
    basic: dict = {"title": title, "year": year}
    if authors is not None:
        basic["authors"] = authors
    if abstract is not None:
        basic["abstract"] = abstract
    md = {
        "metadata": {
            "id": {"doi": doi, "arxiv_id": arxiv_id, "pmid": pmid},
            "basic": basic,
            "publication": {"journal": journal},
            "access": {"is_open_access": is_oa},
            "citation": {"count": citation_count} if citation_count is not None else {},
        }
    }
    (entry / "metadata.json").write_text(json.dumps(md))


def test_build_populates_papers(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa", year=2023, title="Alpha")
    _write_entry(tmp_path, "BBB", pmid="123", year=2024, title="Beta")

    n = idx.build(tmp_path)
    assert n == 2
    assert idx.db_path(tmp_path).exists()

    conn = sqlite3.connect(idx.db_path(tmp_path))
    conn.row_factory = sqlite3.Row
    rows = {r["paper_id"]: dict(r) for r in conn.execute("SELECT * FROM papers")}
    assert rows["AAA"]["doi"] == "10.1/aaa"
    assert rows["BBB"]["pmid"] == "123"
    assert rows["AAA"]["title"] == "Alpha"
    conn.close()


def test_build_is_idempotent(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    idx.build(tmp_path)  # rebuild, no error
    assert idx.lookup_by_doi(tmp_path, "10.1/aaa")["paper_id"] == "AAA"


def test_lookup_by_doi_case_insensitive(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    assert idx.lookup_by_doi(tmp_path, "10.1/AAA") is not None


def test_lookup_missing_returns_none(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    assert idx.lookup_by_doi(tmp_path, "nope") is None
    assert idx.lookup_by_paper_id(tmp_path, "ZZZ") is None


def test_list_all_orders_by_year_desc(tmp_path: Path):
    _write_entry(tmp_path, "OLD", doi="10.1/old", year=2010, title="old")
    _write_entry(tmp_path, "NEW", doi="10.1/new", year=2025, title="new")
    idx.build(tmp_path)
    rows = idx.list_all(tmp_path)
    assert [r["paper_id"] for r in rows] == ["NEW", "OLD"]


def test_empty_string_doi_treated_as_null(tmp_path: Path):
    # Multiple entries with `doi=""` used to raise UNIQUE(doi) in SQLite
    # (NULL is distinct per unique-index semantics, but empty string is a
    # real value and collides). Empty should be normalized to NULL so the
    # index treats "no DOI" consistently regardless of None-vs-"" source.
    _write_entry(tmp_path, "A", doi="", title="alpha")
    _write_entry(tmp_path, "B", doi="", title="beta")
    _write_entry(tmp_path, "C", doi="   ", title="whitespace-only")  # also empty
    n = idx.build(tmp_path)
    assert n == 3
    rows = idx.list_all(tmp_path)
    assert len(rows) == 3
    assert all(r["doi"] is None for r in rows)


def test_duplicate_doi_raises(tmp_path: Path):
    # Two MASTER entries sharing a DOI is library corruption; build() must
    # fail loudly so the user can fix it, rather than silently drop a paper.
    _write_entry(tmp_path, "AAA", doi="10.1/same", title="first")
    _write_entry(tmp_path, "BBB", doi="10.1/same", title="second")
    with pytest.raises(ValueError, match="Duplicate DOIs"):
        idx.build(tmp_path)


def test_duplicate_doi_preserves_existing_db(tmp_path: Path):
    # If a prior build() succeeded and a new duplicate is introduced, the
    # failing rebuild must not wipe the existing DB (atomic swap).
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    assert idx.lookup_by_doi(tmp_path, "10.1/aaa") is not None
    _write_entry(tmp_path, "BBB", doi="10.1/aaa")
    with pytest.raises(ValueError):
        idx.build(tmp_path)
    # Old DB still intact.
    assert idx.lookup_by_doi(tmp_path, "10.1/aaa") is not None


def test_build_populates_enriched_fields(tmp_path: Path):
    _write_entry(
        tmp_path,
        "AAA",
        doi="10.1/aaa",
        authors=["Alice", "Bob"],
        abstract="Summary text.",
        citation_count=42,
    )
    idx.build(tmp_path)
    row = idx.lookup_by_doi(tmp_path, "10.1/aaa")
    assert row is not None
    assert json.loads(row["authors_json"]) == ["Alice", "Bob"]
    assert row["abstract"] == "Summary text."
    assert row["citation_count"] == 42


def test_build_null_enriched_fields_when_absent(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    row = idx.lookup_by_doi(tmp_path, "10.1/aaa")
    assert row is not None
    assert row["authors_json"] is None
    assert row["abstract"] is None
    assert row["citation_count"] is None


def test_build_requires_master_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        idx.build(tmp_path)


def test_migrate_on_fresh_db_creates_schema(tmp_path: Path):
    (tmp_path / "MASTER").mkdir()
    v = idx.migrate(tmp_path)
    assert v == idx.SCHEMA_VERSION


def test_schema_version_persisted(tmp_path: Path):
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    idx.build(tmp_path)
    conn = sqlite3.connect(idx.db_path(tmp_path))
    v = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    conn.close()
    assert int(v) == idx.SCHEMA_VERSION
