#!/usr/bin/env python3
"""Tests for `materialize` / `dematerialize`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_scholar.cli._materialize import (
    _iter_bib_dois,
    _resolve_paper_ids_by_doi,
    dematerialize,
    materialize,
)


def _make_library(root: Path, entries: list[tuple[str, str]]) -> Path:
    """Create a fake scholar library. entries = [(paper_id, doi), ...]."""
    master = root / "MASTER"
    master.mkdir(parents=True)
    for paper_id, doi in entries:
        entry = master / paper_id
        entry.mkdir()
        (entry / "metadata.json").write_text(
            json.dumps({"metadata": {"id": {"doi": doi}}})
        )
        (entry / "paper.pdf").write_bytes(b"%PDF-1.4 stub")
    return root


def test_iter_bib_dois(tmp_path: Path):
    # Arrange
    bib = tmp_path / "refs.bib"
    # Act
    bib.write_text(
        "@article{a, doi={10.1/AAA}}\n"
        '@article{b, doi = "10.2/BBB",}\n'
        "@article{c, title={no doi}}\n"
    )
    # Assert
    assert set(_iter_bib_dois(bib)) == {"10.1/AAA", "10.2/BBB"}


def test_resolve_paper_ids_by_doi(tmp_path: Path):
    # Arrange
    lib = _make_library(tmp_path, [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb")])
    # Act
    mapping = _resolve_paper_ids_by_doi(lib, {"10.1/AAA", "10.2/bbb", "10.9/missing"})
    # Assert
    assert mapping == {"10.1/aaa": "AAAA1111", "10.2/bbb": "BBBB2222"}


def test_materialize_round_trip_n_equals_n_2(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert n == 2


def test_materialize_round_trip_not_path_is_symlink(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert not path.is_symlink()


def test_materialize_round_trip_path_is_dir(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert path.is_dir()


def test_materialize_round_trip_path_master_aaaa1111_paper_pdf_exists(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert (path / "MASTER" / "AAAA1111" / "paper.pdf").exists()


def test_materialize_round_trip_path_master_bbbb2222_paper_pdf_exists(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert (path / "MASTER" / "BBBB2222" / "paper.pdf").exists()


def test_materialize_round_trip_not_path_master_cccc3333_exists(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    # Act
    n, path = materialize(link, bib)
    # Act
    # Assert
    assert not (path / "MASTER" / "CCCC3333").exists()


def test_materialize_round_trip_path_is_symlink(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    n, path = materialize(link, bib)
    # Act
    dematerialize(path, target=home_lib)
    # Act
    # Assert
    assert path.is_symlink()


def test_materialize_round_trip_path_resolve_home_lib_resolve(tmp_path: Path):
    # Arrange
    home_lib = _make_library(
        tmp_path / "home",
        [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb"), ("CCCC3333", "10.3/ccc")],
    )
    link = tmp_path / "project" / "library"
    link.parent.mkdir()
    link.symlink_to(home_lib)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}\n@article{b, doi={10.2/BBB}}\n")
    n, path = materialize(link, bib)
    # Act
    dematerialize(path, target=home_lib)
    # Act
    # Assert
    assert path.resolve() == home_lib.resolve()




def test_materialize_rejects_non_symlink(tmp_path: Path):
    # Arrange
    real = tmp_path / "real"
    real.mkdir()
    bib = tmp_path / "x.bib"
    # Act
    bib.write_text("@article{a, doi={10.1/aaa}}")
    # Assert
    with pytest.raises(FileExistsError):
        materialize(real, bib)


def test_dematerialize_rejects_symlink(tmp_path: Path):
    # Arrange
    target = tmp_path / "t"
    target.mkdir()
    link = tmp_path / "link"
    # Act
    link.symlink_to(target)
    # Assert
    with pytest.raises(FileExistsError):
        dematerialize(link)
