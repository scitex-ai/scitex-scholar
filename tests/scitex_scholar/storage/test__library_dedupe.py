#!/usr/bin/env python3
"""Tests for duplicate-DOI resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_scholar.storage._library_dedupe import (
    DedupePlan,
    apply_plan,
    format_plan,
    plan_dedupe,
)


def _write(
    root: Path,
    paper_id: str,
    *,
    doi: str,
    title: str | None = "t",
    authors: list[str] | None = None,
    abstract: str | None = None,
    year: int | None = 2024,
    citations: int | None = None,
    pmid: str | None = None,
    arxiv_id: str | None = None,
    with_pdf: bool = False,
) -> Path:
    entry = root / "MASTER" / paper_id
    entry.mkdir(parents=True)
    basic: dict = {}
    if title is not None:
        basic["title"] = title
    if authors:
        basic["authors"] = authors
    if abstract is not None:
        basic["abstract"] = abstract
    if year is not None:
        basic["year"] = year
    md = {
        "metadata": {
            "id": {"doi": doi, "pmid": pmid, "arxiv_id": arxiv_id},
            "basic": basic,
            "citation_count": {"total": citations} if citations else {},
            "path": {"pdfs": [f"{paper_id}.pdf"]} if with_pdf else {},
        }
    }
    (entry / "metadata.json").write_text(json.dumps(md))
    if with_pdf:
        (entry / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4 stub")
    return entry


def test_empty_library_no_decisions(tmp_path: Path):
    # Arrange
    (tmp_path / "MASTER").mkdir()
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert plan.decisions == []


def test_no_duplicates_no_decisions(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert plan.decisions == []


def test_pdf_beats_no_pdf_len_plan_decisions_is_1(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x", with_pdf=False)
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    # Act
    plan = plan_dedupe(tmp_path)
    # Act
    # Assert
    assert len(plan.decisions) == 1


def test_pdf_beats_no_pdf_d_winner_paper_id_equals_rich(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x", with_pdf=False)
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    d = plan.decisions[0]
    # Act
    # Assert
    assert d.winner_paper_id == "RICH"


def test_pdf_beats_no_pdf_lo_paper_id_for_lo_in_d_losers_poor(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x", with_pdf=False)
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    d = plan.decisions[0]
    # Act
    # Assert
    assert [lo["paper_id"] for lo in d.losers] == ["POOR"]




def test_more_populated_metadata_wins(tmp_path: Path):
    # Arrange
    _write(tmp_path, "SPARSE", doi="10.1/same", title="x")
    _write(
        tmp_path,
        "FULL",
        doi="10.1/same",
        title="x",
        authors=["A. Author"],
        abstract="Long abstract.",
        year=2024,
    )
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert plan.decisions[0].winner_paper_id == "FULL"


def test_higher_citation_count_wins_on_ties(tmp_path: Path):
    # Arrange
    _write(tmp_path, "LOW", doi="10.1/same", title="x", citations=5)
    _write(tmp_path, "HIGH", doi="10.1/same", title="x", citations=500)
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert plan.decisions[0].winner_paper_id == "HIGH"


def test_more_ids_wins(tmp_path: Path):
    # Arrange
    _write(tmp_path, "NOIDS", doi="10.1/same", title="x")
    _write(
        tmp_path, "HASIDS", doi="10.1/same", title="x", pmid="123", arxiv_id="2401.001"
    )
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert plan.decisions[0].winner_paper_id == "HASIDS"


def test_case_insensitive_doi_match(tmp_path: Path):
    # Arrange
    _write(tmp_path, "AAA", doi="10.1/Same")
    _write(tmp_path, "BBB", doi="10.1/same")
    # Act
    plan = plan_dedupe(tmp_path)
    # Assert
    assert len(plan.decisions) == 1


def test_apply_quarantines_losers_moved_equals_n_1(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    moved = apply_plan(tmp_path, plan)
    # Act
    # Assert
    assert moved == 1


def test_apply_quarantines_losers_not_tmp_path_master_poor_exists(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    moved = apply_plan(tmp_path, plan)
    # Act
    # Assert
    assert not (tmp_path / "MASTER" / "POOR").exists()


def test_apply_quarantines_losers_tmp_path_master_quarantine_poor_exists(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    moved = apply_plan(tmp_path, plan)
    # Act
    # Assert
    assert (tmp_path / "MASTER_quarantine" / "POOR").exists()


def test_apply_quarantines_losers_tmp_path_master_rich_exists(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    moved = apply_plan(tmp_path, plan)
    # Act
    # Assert
    assert (tmp_path / "MASTER" / "RICH").exists()




def test_apply_hard_delete_removes_losers_not_tmp_path_master_poor_exists(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    apply_plan(tmp_path, plan, hard_delete=True)
    # Act
    # Assert
    assert not (tmp_path / "MASTER" / "POOR").exists()


def test_apply_hard_delete_removes_losers_not_tmp_path_master_quarantine_poor_exists(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    # Act
    apply_plan(tmp_path, plan, hard_delete=True)
    # Act
    # Assert
    assert not (tmp_path / "MASTER_quarantine" / "POOR").exists()




def test_apply_is_idempotent(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan)
    # Second run: loser already gone, nothing to do
    # Act
    plan2 = plan_dedupe(tmp_path)
    # Assert
    assert plan2.decisions == []


def test_format_plan_dry_run_dry_run_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", with_pdf=True)
    # Act
    text = format_plan(plan_dedupe(tmp_path))
    # Act
    # Assert
    assert "DRY RUN" in text


def test_format_plan_dry_run_apply_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", with_pdf=True)
    # Act
    text = format_plan(plan_dedupe(tmp_path))
    # Act
    # Assert
    assert "--apply" in text


def test_format_plan_dry_run_winner_b_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", with_pdf=True)
    # Act
    text = format_plan(plan_dedupe(tmp_path))
    # Act
    # Assert
    assert "winner: B" in text


def test_format_plan_dry_run_loser_a_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", with_pdf=True)
    # Act
    text = format_plan(plan_dedupe(tmp_path))
    # Act
    # Assert
    assert "loser : A" in text




def test_format_plan_empty(tmp_path: Path):
    # Arrange
    (tmp_path / "MASTER").mkdir()
    # Act
    text = format_plan(plan_dedupe(tmp_path))
    # Assert
    assert "No duplicate DOIs found" in text


def test_plan_after_apply_marks_applied_applied_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan)
    # Act
    text = format_plan(plan)
    # Act
    # Assert
    assert "APPLIED" in text


def test_plan_after_apply_marks_applied_moved_1_entries_in_text(tmp_path: Path):
    # Arrange
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan)
    # Act
    text = format_plan(plan)
    # Act
    # Assert
    assert "Moved 1 entries" in text




def test_missing_master_raises(tmp_path: Path):
    # Arrange
    # Act
    # Assert
    with pytest.raises(FileNotFoundError):
        plan_dedupe(tmp_path)


def test_three_way_collision_picks_single_winner_plan_decisions_0_winner_paper_id_c(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", authors=["A"])
    _write(tmp_path, "C", doi="10.1/same", title="x", with_pdf=True)
    # Act
    plan = plan_dedupe(tmp_path)
    # Act
    # Assert
    assert plan.decisions[0].winner_paper_id == "C"


def test_three_way_collision_picks_single_winner_len_plan_decisions_0_los_is_2(tmp_path: Path):
    # Arrange
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", authors=["A"])
    _write(tmp_path, "C", doi="10.1/same", title="x", with_pdf=True)
    # Act
    plan = plan_dedupe(tmp_path)
    # Act
    # Assert
    assert len(plan.decisions[0].losers) == 2




def test_dedupe_plan_dataclass_defaults_p_decisions_equals_case():
    # Arrange
    # Act
    p = DedupePlan()
    # Act
    # Assert
    assert p.decisions == []


def test_dedupe_plan_dataclass_defaults_p_dry_run_is_true():
    # Arrange
    # Act
    p = DedupePlan()
    # Act
    # Assert
    assert p.dry_run is True


def test_dedupe_plan_dataclass_defaults_p_loser_paper_ids_equals_case():
    # Arrange
    # Act
    p = DedupePlan()
    # Act
    # Assert
    assert p.loser_paper_ids == []


