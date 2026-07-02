#!/usr/bin/env python3
"""Tests for the `library dedupe` CLI leaf.

Mirrors `src/scitex_scholar/_cli/library.py`. Drives the REAL dedupe code
path over a tiny temp library (two duplicate-DOI MASTER entries) via
`--library-root`, so no monkeypatch is needed. Verifies the exit-code
contract a production cron pre-sync gate depends on:

- dry-run with conflicts  -> non-zero exit, plan lists the conflict.
- dry-run on a clean tree  -> exit 0.
- --apply on conflicts     -> exit 0, loser quarantined.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scitex_scholar._cli_main import cli


def _make_entry(root: Path, paper_id: str, *, doi: str, with_pdf: bool) -> None:
    """Create a MASTER/<paper_id>/metadata.json (and optional PDF)."""
    entry = root / "MASTER" / paper_id
    entry.mkdir(parents=True)
    md = {
        "metadata": {
            "id": {"doi": doi},
            "basic": {"title": "t", "year": 2024},
            "path": {"pdfs": [f"{paper_id}.pdf"]} if with_pdf else {},
        }
    }
    (entry / "metadata.json").write_text(json.dumps(md))
    if with_pdf:
        (entry / f"{paper_id}.pdf").write_bytes(b"%PDF-1.4 stub")


def _library_with_duplicate(root: Path) -> None:
    """Two MASTER entries sharing one DOI (RICH has a PDF, so it wins)."""
    _make_entry(root, "POOR", doi="10.1/dup", with_pdf=False)
    _make_entry(root, "RICH", doi="10.1/dup", with_pdf=True)


def test_dry_run_with_conflict_exits_non_zero(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--dry-run"]
    )
    # Assert
    assert result.exit_code != 0


def test_dry_run_with_conflict_lists_the_conflicting_doi(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--dry-run"]
    )
    # Assert
    assert "10.1/dup" in result.output


def test_default_mode_with_conflict_exits_non_zero(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path)]
    )
    # Assert
    assert result.exit_code != 0


def test_dry_run_on_clean_library_exits_zero(tmp_path: Path):
    # Arrange
    _make_entry(tmp_path, "AAA", doi="10.1/aaa", with_pdf=False)
    _make_entry(tmp_path, "BBB", doi="10.2/bbb", with_pdf=False)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--dry-run"]
    )
    # Assert
    assert result.exit_code == 0


def test_apply_with_conflict_exits_zero(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--apply"]
    )
    # Assert
    assert result.exit_code == 0


def test_apply_removes_loser_from_master(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--apply"]
    )
    # Assert
    assert not (tmp_path / "MASTER" / "POOR").exists()


def test_apply_quarantines_loser(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--apply"]
    )
    # Assert
    assert (tmp_path / "MASTER_quarantine" / "POOR").exists()


def test_apply_keeps_winner_in_master(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--apply"]
    )
    # Assert
    assert (tmp_path / "MASTER" / "RICH").exists()


def test_apply_prints_quarantine_summary(tmp_path: Path):
    # Arrange
    _library_with_duplicate(tmp_path)
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--apply"]
    )
    # Assert
    assert "1 entries quarantined" in result.output


def test_missing_master_dir_fails_loud(tmp_path: Path):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["library", "dedupe", "--library-root", str(tmp_path), "--dry-run"]
    )
    # Assert
    assert result.exit_code != 0
