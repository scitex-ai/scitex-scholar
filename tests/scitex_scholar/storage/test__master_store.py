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

import pytest

from scitex_scholar.storage import _master_store as ms


def test_paper_id_for_doi():
    assert ms.paper_id_for("10.1000/xyz:123", "doi") == "doi-10.1000_xyz_123"


def test_paper_id_for_fallback():
    assert ms.paper_id_for("", "") == "unknown"


def test_add_paper_writes_master_with_metadata(tmp_path):
    result = ms.add_paper(
        tmp_path,
        "10.1000/demo",
        "doi",
        bibtex_content="@article{demo, title={Demo}}",
        metadata={
            "basic": {"title": "Demo Paper", "year": 2024},
            "publication": {"journal": "J Demo"},
        },
    )
    assert str(result["bibtex"]).startswith("MASTER/")
    assert "pdf" not in result
    entry = tmp_path / "MASTER" / "doi-10.1000_demo"
    assert (entry / "doi-10.1000_demo.bib").exists()
    meta = json.loads((entry / "metadata.json").read_text())["metadata"]
    assert meta["basic"]["title"] == "Demo Paper"
    assert meta["id"]["doi"] == "10.1000/demo"


def test_add_paper_flat_metadata_folds(tmp_path):
    result = ms.add_paper(
        tmp_path,
        "10.1000/flat",
        "doi",
        bibtex_content="@article{flat, title={Flat}}",
        metadata={"title": "Flat Paper", "year": 2023},
    )
    meta = json.loads(
        (tmp_path / result["bibtex"]).parent.joinpath("metadata.json").read_text()
    )["metadata"]
    assert meta["basic"]["title"] == "Flat Paper"
    assert meta["basic"]["year"] == 2023


def test_add_paper_nested_wins_over_flat(tmp_path):
    result = ms.add_paper(
        tmp_path,
        "10.1000/both",
        "doi",
        metadata={"title": "Flat", "basic": {"title": "Nested"}},
    )
    meta = json.loads(
        (tmp_path / "MASTER" / "doi-10.1000_both" / "metadata.json").read_text()
    )["metadata"]
    assert meta["basic"]["title"] == "Nested"


def test_get_paper_path_roundtrip(tmp_path):
    assert ms.get_paper_path(tmp_path, "10.1000/x", "doi", "bib") is None
    ms.add_paper(
        tmp_path, "10.1000/x", "doi", bibtex_content="@article{x, title={X}}"
    )
    found = ms.get_paper_path(tmp_path, "10.1000/x", "doi", "bib")
    assert found is not None and found.name == "doi-10.1000_x.bib"


def test_list_papers_master_and_legacy(tmp_path):
    ms.add_paper(tmp_path, "10.1000/a", "doi")
    legacy = tmp_path / "papers" / "doi"
    legacy.mkdir(parents=True)
    (legacy / "10.9999_b.pdf").write_text("pdf")
    rows = ms.list_papers(tmp_path)
    kinds = {(r["identifier"], r["id_type"]) for r in rows}
    assert ("doi-10.1000_a", "master") not in kinds  # no PDF written
    assert ("10.9999_b", "doi") in kinds


def test_index_hook_failure_is_silent(tmp_path, monkeypatch):
    import scitex_scholar.storage._library_index as idx

    monkeypatch.setattr(
        idx, "_open_store", lambda: (_ for _ in ()).throw(ConnectionError("down"))
    )
    ms.add_paper(tmp_path, "10.1000/q", "doi")
    assert (tmp_path / "MASTER" / "doi-10.1000_q").is_dir()
