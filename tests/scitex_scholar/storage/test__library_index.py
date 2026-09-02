#!/usr/bin/env python3
"""Tests for the library index's derivation from MASTER metadata.

WHAT THESE TESTS COVER, AND WHAT THEY DELIBERATELY DO NOT
---------------------------------------------------------
The index has two halves. One DERIVES rows from
``MASTER/<paper_id>/metadata.json`` — identifier normalisation, field
extraction, duplicate-DOI detection, ordering. The other WRITES those rows
to :mod:`scitex_dev.store`. All of the logic is in the first half, and it
is pure, so it is tested here directly.

The store half is not tested here. ``host_store()`` resolves to the fleet
PostgreSQL and deliberately has no local fallback, and this project's CI runs
on GitHub-hosted ``ubuntu-latest`` runners that cannot reach it — a test
touching the store would fail there for a reason that has nothing to do with
the code under test. Rather than skip it (a skip that always skips reads as
coverage and is not), the split is explicit: everything below runs
everywhere, and the round-trip through the store is verified by hand against
a live store when the index changes.
"""

from __future__ import annotations

import json
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


def _by_paper_id(rows: list[dict]) -> dict[str, dict]:
    return {r["paper_id"]: r for r in rows}


# ----- collect_rows --------------------------------------------------------


def test_collect_rows_returns_one_row_per_master_entry(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/aaa", year=2023, title="Alpha")
    _write_entry(tmp_path, "BBB", pmid="123", year=2024, title="Beta")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert len(rows) == 2


def test_collect_rows_carries_the_doi(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/aaa")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert _by_paper_id(rows)["AAA"]["doi"] == "10.1/aaa"


def test_collect_rows_carries_the_pmid(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "BBB", pmid="123")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert _by_paper_id(rows)["BBB"]["pmid"] == "123"


def test_collect_rows_carries_the_title(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", title="Alpha")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert _by_paper_id(rows)["AAA"]["title"] == "Alpha"


def test_collect_rows_keys_every_row_by_the_resolved_library_root(tmp_path: Path):
    """``library_root`` is half the record identity, so it must be canonical.

    One store serves every library on the host. If two roots that are the
    same directory reached by different paths produced different keys, the
    same paper would occupy two rows and the second build would not replace
    the first.
    """
    # Arrange
    _write_entry(tmp_path, "AAA")
    indirect = tmp_path / "sub" / ".."
    indirect.mkdir(parents=True, exist_ok=True)
    # Act
    direct_rows = idx.collect_rows(tmp_path)
    indirect_rows = idx.collect_rows(indirect)
    # Assert
    assert direct_rows[0]["library_root"] == indirect_rows[0]["library_root"]


def test_collect_rows_prefers_short_journal_for_venue(tmp_path: Path):
    # Arrange
    entry = tmp_path / "MASTER" / "AAA"
    entry.mkdir(parents=True)
    (entry / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "publication": {"journal": "Long Name", "short_journal": "LN"}
                }
            }
        )
    )
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["venue"] == "LN"


def test_collect_rows_skips_unreadable_metadata(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "GOOD", doi="10.1/good")
    broken = tmp_path / "MASTER" / "BROKEN"
    broken.mkdir(parents=True)
    (broken / "metadata.json").write_text("{not json")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert [r["paper_id"] for r in rows] == ["GOOD"]


def test_collect_rows_requires_master_dir(tmp_path: Path):
    # Arrange
    root = tmp_path  # no MASTER/ written

    # Act
    def act():
        idx.collect_rows(root)

    # Assert
    with pytest.raises(FileNotFoundError):
        act()


# ----- identifier normalisation -------------------------------------------


def test_empty_string_doi_becomes_none(tmp_path: Path):
    """`""` is not an identifier, and treating it as one merges papers.

    Several library entries legitimately have no DOI. Carrying `""` through
    makes every one of them look like the same paper.
    """
    # Arrange
    _write_entry(tmp_path, "AAA", doi="")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["doi"] is None


def test_whitespace_only_arxiv_id_becomes_none(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", arxiv_id="   ")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["arxiv_id"] is None


def test_several_empty_doi_entries_all_survive(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="")
    _write_entry(tmp_path, "BBB", doi="")
    _write_entry(tmp_path, "CCC", doi=None)
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert len(rows) == 3


def test_padded_doi_is_stripped(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="  10.1/aaa  ")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["doi"] == "10.1/aaa"


# ----- duplicate DOIs ------------------------------------------------------


def _duplicate_doi_message(root: Path) -> str:
    """Return the message ``collect_rows`` refuses a duplicated DOI with."""
    try:
        idx.collect_rows(root)
    except ValueError as exc:
        return str(exc)
    return ""


def test_duplicate_doi_raises(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/dup")
    _write_entry(tmp_path, "BBB", doi="10.1/dup")

    # Act
    def act():
        idx.collect_rows(tmp_path)

    # Assert
    with pytest.raises(ValueError, match="Duplicate DOIs"):
        act()


def test_duplicate_doi_detection_is_case_insensitive(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/DUP")
    _write_entry(tmp_path, "BBB", doi="10.1/dup")

    # Act
    def act():
        idx.collect_rows(tmp_path)

    # Assert
    with pytest.raises(ValueError, match="Duplicate DOIs"):
        act()


def test_duplicate_doi_message_names_the_first_paper(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/dup")
    _write_entry(tmp_path, "BBB", doi="10.1/dup")
    # Act
    message = _duplicate_doi_message(tmp_path)
    # Assert
    assert "AAA" in message


def test_duplicate_doi_message_names_the_second_paper(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/dup")
    _write_entry(tmp_path, "BBB", doi="10.1/dup")
    # Act
    message = _duplicate_doi_message(tmp_path)
    # Assert
    assert "BBB" in message


def test_duplicate_doi_is_detected_before_any_row_is_written(tmp_path: Path):
    """A corrupt library must not be able to damage rows already indexed.

    ``build()`` calls ``collect_rows()`` first and only opens the store
    afterwards, so this raising BEFORE returning any rows is what makes the
    previous index survive a failed rebuild.
    """
    # Arrange
    _write_entry(tmp_path, "AAA", doi="10.1/dup")
    _write_entry(tmp_path, "BBB", doi="10.1/dup")
    # Act
    raised = None
    try:
        idx.collect_rows(tmp_path)
    except ValueError as exc:
        raised = exc
    # Assert
    assert raised is not None


# ----- enriched fields -----------------------------------------------------


def test_authors_round_trip_as_a_json_array(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", authors=["Alice", "Bob"])
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert json.loads(rows[0]["authors_json"]) == ["Alice", "Bob"]


def test_abstract_is_carried(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", abstract="An abstract.")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["abstract"] == "An abstract."


def test_citation_count_is_carried(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", citation_count=42)
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["citation_count"] == 42


def test_authors_absent_yields_none(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["authors_json"] is None


def test_abstract_absent_yields_none(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["abstract"] is None


def test_citation_count_absent_yields_none(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA")
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["citation_count"] is None


def test_is_oa_absent_yields_none_not_false(tmp_path: Path):
    """"Unknown" and "not open access" are different answers."""
    # Arrange
    entry = tmp_path / "MASTER" / "AAA"
    entry.mkdir(parents=True)
    (entry / "metadata.json").write_text(json.dumps({"metadata": {"access": {}}}))
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["is_oa"] is None


def test_is_oa_true_becomes_one(tmp_path: Path):
    # Arrange
    _write_entry(tmp_path, "AAA", is_oa=True)
    # Act
    rows = idx.collect_rows(tmp_path)
    # Assert
    assert rows[0]["is_oa"] == 1


# ----- ordering ------------------------------------------------------------


def test_sort_key_puts_the_newest_year_first():
    # Arrange
    rows = [{"year": 1999, "title": "old"}, {"year": 2024, "title": "new"}]
    # Act
    ordered = sorted(rows, key=idx.sort_key)
    # Assert
    assert [r["title"] for r in ordered] == ["new", "old"]


def test_sort_key_breaks_year_ties_by_title():
    # Arrange
    rows = [{"year": 2024, "title": "b"}, {"year": 2024, "title": "a"}]
    # Act
    ordered = sorted(rows, key=idx.sort_key)
    # Assert
    assert [r["title"] for r in ordered] == ["a", "b"]


def test_sort_key_puts_an_unknown_year_last_not_first():
    """An unknown year is not year zero."""
    # Arrange
    rows = [{"year": None, "title": "undated"}, {"year": 1900, "title": "ancient"}]
    # Act
    ordered = sorted(rows, key=idx.sort_key)
    # Assert
    assert [r["title"] for r in ordered] == ["ancient", "undated"]


# ----- schema --------------------------------------------------------------


def test_schema_declares_every_field_the_rows_carry(tmp_path: Path):
    """A row field the schema does not declare is a hard error on write.

    ``Store.put`` raises on an undeclared field rather than dropping it, so
    a mismatch between what ``collect_rows`` produces and what ``schema()``
    declares stops a rebuild outright. Catching it here is cheaper than
    catching it against a live store.
    """
    # Arrange
    pytest.importorskip("scitex_dev.store")
    _write_entry(tmp_path, "AAA", doi="10.1/aaa", authors=["Alice"], abstract="a")
    # Act
    declared = set(idx.schema().fields)
    produced = set(idx.collect_rows(tmp_path)[0])
    # Assert
    assert produced == declared


def test_schema_identity_is_library_root_plus_paper_id():
    # Arrange
    pytest.importorskip("scitex_dev.store")
    # Act
    identity = list(idx.schema().identity_fields)
    # Assert
    assert identity == ["library_root", "paper_id"]


# EOF
