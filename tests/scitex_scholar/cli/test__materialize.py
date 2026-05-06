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
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{a, doi={10.1/AAA}}\n"
        '@article{b, doi = "10.2/BBB",}\n'
        "@article{c, title={no doi}}\n"
    )
    assert set(_iter_bib_dois(bib)) == {"10.1/AAA", "10.2/BBB"}


def test_resolve_paper_ids_by_doi(tmp_path: Path):
    lib = _make_library(tmp_path, [("AAAA1111", "10.1/aaa"), ("BBBB2222", "10.2/bbb")])
    mapping = _resolve_paper_ids_by_doi(lib, {"10.1/AAA", "10.2/bbb", "10.9/missing"})
    assert mapping == {"10.1/aaa": "AAAA1111", "10.2/bbb": "BBBB2222"}


def test_materialize_round_trip(tmp_path: Path):
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
    assert n == 2
    assert not path.is_symlink()
    assert path.is_dir()
    assert (path / "MASTER" / "AAAA1111" / "paper.pdf").exists()
    assert (path / "MASTER" / "BBBB2222" / "paper.pdf").exists()
    assert not (path / "MASTER" / "CCCC3333").exists()

    dematerialize(path, target=home_lib)
    assert path.is_symlink()
    assert path.resolve() == home_lib.resolve()


def test_materialize_rejects_non_symlink(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    bib = tmp_path / "x.bib"
    bib.write_text("@article{a, doi={10.1/aaa}}")
    with pytest.raises(FileExistsError):
        materialize(real, bib)


def test_dematerialize_rejects_symlink(tmp_path: Path):
    target = tmp_path / "t"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(FileExistsError):
        dematerialize(link)
