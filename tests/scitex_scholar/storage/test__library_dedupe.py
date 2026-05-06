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
    (tmp_path / "MASTER").mkdir()
    plan = plan_dedupe(tmp_path)
    assert plan.decisions == []


def test_no_duplicates_no_decisions(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/aaa")
    _write(tmp_path, "BBB", doi="10.2/bbb")
    plan = plan_dedupe(tmp_path)
    assert plan.decisions == []


def test_pdf_beats_no_pdf(tmp_path: Path):
    _write(tmp_path, "POOR", doi="10.1/same", title="x", with_pdf=False)
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    assert len(plan.decisions) == 1
    d = plan.decisions[0]
    assert d.winner_paper_id == "RICH"
    assert [lo["paper_id"] for lo in d.losers] == ["POOR"]


def test_more_populated_metadata_wins(tmp_path: Path):
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
    plan = plan_dedupe(tmp_path)
    assert plan.decisions[0].winner_paper_id == "FULL"


def test_higher_citation_count_wins_on_ties(tmp_path: Path):
    _write(tmp_path, "LOW", doi="10.1/same", title="x", citations=5)
    _write(tmp_path, "HIGH", doi="10.1/same", title="x", citations=500)
    plan = plan_dedupe(tmp_path)
    assert plan.decisions[0].winner_paper_id == "HIGH"


def test_more_ids_wins(tmp_path: Path):
    _write(tmp_path, "NOIDS", doi="10.1/same", title="x")
    _write(
        tmp_path, "HASIDS", doi="10.1/same", title="x", pmid="123", arxiv_id="2401.001"
    )
    plan = plan_dedupe(tmp_path)
    assert plan.decisions[0].winner_paper_id == "HASIDS"


def test_case_insensitive_doi_match(tmp_path: Path):
    _write(tmp_path, "AAA", doi="10.1/Same")
    _write(tmp_path, "BBB", doi="10.1/same")
    plan = plan_dedupe(tmp_path)
    assert len(plan.decisions) == 1


def test_apply_quarantines_losers(tmp_path: Path):
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    moved = apply_plan(tmp_path, plan)
    assert moved == 1
    assert not (tmp_path / "MASTER" / "POOR").exists()
    assert (tmp_path / "MASTER_quarantine" / "POOR").exists()
    assert (tmp_path / "MASTER" / "RICH").exists()


def test_apply_hard_delete_removes_losers(tmp_path: Path):
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan, hard_delete=True)
    assert not (tmp_path / "MASTER" / "POOR").exists()
    assert not (tmp_path / "MASTER_quarantine" / "POOR").exists()


def test_apply_is_idempotent(tmp_path: Path):
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan)
    # Second run: loser already gone, nothing to do
    plan2 = plan_dedupe(tmp_path)
    assert plan2.decisions == []


def test_format_plan_dry_run(tmp_path: Path):
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", with_pdf=True)
    text = format_plan(plan_dedupe(tmp_path))
    assert "DRY RUN" in text
    assert "--apply" in text
    assert "winner: B" in text
    assert "loser : A" in text


def test_format_plan_empty(tmp_path: Path):
    (tmp_path / "MASTER").mkdir()
    text = format_plan(plan_dedupe(tmp_path))
    assert "No duplicate DOIs found" in text


def test_plan_after_apply_marks_applied(tmp_path: Path):
    _write(tmp_path, "POOR", doi="10.1/same", title="x")
    _write(tmp_path, "RICH", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    apply_plan(tmp_path, plan)
    text = format_plan(plan)
    assert "APPLIED" in text
    assert "Moved 1 entries" in text


def test_missing_master_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        plan_dedupe(tmp_path)


def test_three_way_collision_picks_single_winner(tmp_path: Path):
    _write(tmp_path, "A", doi="10.1/same", title="x")
    _write(tmp_path, "B", doi="10.1/same", title="x", authors=["A"])
    _write(tmp_path, "C", doi="10.1/same", title="x", with_pdf=True)
    plan = plan_dedupe(tmp_path)
    assert plan.decisions[0].winner_paper_id == "C"
    assert len(plan.decisions[0].losers) == 2


def test_dedupe_plan_dataclass_defaults():
    p = DedupePlan()
    assert p.decisions == []
    assert p.dry_run is True
    assert p.loser_paper_ids == []
