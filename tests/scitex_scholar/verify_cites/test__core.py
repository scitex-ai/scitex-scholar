#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__core.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._core (end-to-end orchestration)."""
from __future__ import annotations

import json

import pytest

vc_core = pytest.importorskip("scitex_scholar.verify_cites._core")
from scitex_scholar.verify_cites._core import (  # noqa: E402
    build_citations_artifact,
    compute_exit_code,
    push_to_clew,
    verify_cites,
)
from scitex_scholar.verify_cites._model import (  # noqa: E402
    EXIT_CITATION_STUB,
    EXIT_CITATION_UNLINKED,
    EXIT_NO_CITES,
    EXIT_OK,
    HALLUCINATED,
    STUB,
    UNLINKED,
    VERIFIED,
)
from scitex_scholar.verify_cites._resolve import ResolvedRef  # noqa: E402


def _fake_resolver(entry):
    """Resolve anything carrying a DOI to a title matching the bib title."""
    if (entry.get("doi") or "").strip():
        return ResolvedRef(title=entry.get("title"), doi=entry["doi"], source="crossref")
    return None


@pytest.fixture
def e2e(tmp_path):
    """Run verify_cites over a verified + stub + hallucinated mix."""
    entries = {
        "Good2020": {"title": "A real verified paper", "doi": "10.1/good"},
        "Stubby2021": {
            "title": "[Stub] Stubby",
            "journal": "Pending scitex-scholar metadata lookup",
        },
        "Ghost2099": {"title": "A fabricated one", "author": "Nobody"},
    }
    out = tmp_path / "citation_status.json"
    report = verify_cites(
        tmp_path,
        entries=entries,
        cited_keys=["Good2020", "Stubby2021", "Ghost2099"],
        resolver=_fake_resolver,
        out=out,
        min_confidence=0.6,
    )
    return report, out


def test_verify_cites_marks_verified(e2e):
    # Arrange
    report, _ = e2e
    # Act
    verified = report.by_status(VERIFIED)
    # Assert
    assert verified == ["Good2020"]


def test_verify_cites_marks_stub(e2e):
    # Arrange
    report, _ = e2e
    # Act
    stubs = report.by_status(STUB)
    # Assert
    assert stubs == ["Stubby2021"]


def test_verify_cites_marks_hallucinated(e2e):
    # Arrange
    report, _ = e2e
    # Act
    halluc = report.by_status(HALLUCINATED)
    # Assert
    assert halluc == ["Ghost2099"]


def test_verify_cites_writes_sidecar_keyed_by_bibkey(e2e):
    # Arrange
    _, out = e2e
    # Act
    data = json.loads(out.read_text())
    # Assert
    assert set(data) == {"Good2020", "Stubby2021", "Ghost2099"}


def test_verify_cites_sidecar_records_status(e2e):
    # Arrange
    _, out = e2e
    # Act
    data = json.loads(out.read_text())
    # Assert
    assert data["Good2020"]["status"] == VERIFIED


def test_verify_cites_gate_stub_hallucinated_maps_to_14(e2e):
    # Arrange
    report, _ = e2e
    # Act
    rc = compute_exit_code(report, ["stub", "hallucinated"])
    # Assert
    assert rc == EXIT_CITATION_STUB


def test_verify_cites_all_verified_returns_ok(tmp_path):
    # Arrange
    entries = {"A": {"title": "Paper A", "doi": "10.1/a"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["A"], resolver=_fake_resolver,
        out=tmp_path / "s.json", min_confidence=0.6,
    )
    # Act
    rc = compute_exit_code(report, ["stub", "hallucinated"])
    # Assert
    assert rc == EXIT_OK


def test_verify_cites_cited_but_absent_is_unlinked(tmp_path):
    # Arrange
    report = verify_cites(
        tmp_path, entries={}, cited_keys=["Missing2020"], resolver=_fake_resolver,
        out=tmp_path / "s.json",
    )
    # Act
    unlinked = report.by_status(UNLINKED)
    # Assert
    assert unlinked == ["Missing2020"]


def test_verify_cites_unlinked_gate_maps_to_16(tmp_path):
    # Arrange
    report = verify_cites(
        tmp_path, entries={}, cited_keys=["Missing2020"], resolver=_fake_resolver,
        out=tmp_path / "s.json",
    )
    # Act
    rc = compute_exit_code(report, ["unlinked"])
    # Assert
    assert rc == EXIT_CITATION_UNLINKED


def test_verify_cites_no_cites_exit_code(tmp_path):
    # Arrange
    report = verify_cites(
        tmp_path, entries={}, cited_keys=[], resolver=_fake_resolver,
        out=tmp_path / "s.json",
    )
    # Act
    rc = compute_exit_code(report, ["stub", "hallucinated"])
    # Assert
    assert rc == EXIT_NO_CITES


def test_verify_cites_stub_only_gate_exit_code(tmp_path):
    # Arrange
    entries = {"S": {"title": "[Stub] S", "note": "Auto-generated stub"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["S"], resolver=_fake_resolver,
        out=tmp_path / "s.json",
    )
    # Act
    rc = compute_exit_code(report, ["stub"])
    # Assert
    assert rc == EXIT_CITATION_STUB


def test_build_citations_artifact_carries_schema_marker(tmp_path):
    # Arrange
    entries = {"A": {"title": "Paper A", "doi": "10.1/a"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["A"], resolver=_fake_resolver,
        out=tmp_path / "s.json", min_confidence=0.6,
    )
    # Act
    artifact = build_citations_artifact(report)
    # Assert
    assert artifact["schema"] == "scitex-clew/citations/v1"


def test_build_citations_artifact_entry_matches_to_clew_shape(tmp_path):
    # Arrange
    entries = {"A": {"title": "Paper A", "doi": "10.1/a"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["A"], resolver=_fake_resolver,
        out=tmp_path / "s.json", min_confidence=0.6,
    )
    # Act
    artifact = build_citations_artifact(report)
    # Assert
    assert artifact["citations"][0]["cite_key"] == "A" and "status" not in artifact["citations"][0]


def test_push_to_clew_writes_sidecar_with_entry_count(tmp_path):
    # Arrange
    entries = {"A": {"title": "Paper A", "doi": "10.1/a"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["A"], resolver=_fake_resolver,
        out=tmp_path / "s.json", min_confidence=0.6,
    )
    clew_out = tmp_path / "citations_clew.json"
    # Act
    pushed = push_to_clew(report, out=clew_out)
    # Assert
    assert pushed == 1


def test_push_to_clew_sidecar_file_carries_schema_marker(tmp_path):
    # Arrange
    entries = {"A": {"title": "Paper A", "doi": "10.1/a"}}
    report = verify_cites(
        tmp_path, entries=entries, cited_keys=["A"], resolver=_fake_resolver,
        out=tmp_path / "s.json", min_confidence=0.6,
    )
    clew_out = tmp_path / "citations_clew.json"
    push_to_clew(report, out=clew_out)
    # Act
    data = json.loads(clew_out.read_text())
    # Assert
    assert data["schema"] == "scitex-clew/citations/v1"


def test_push_to_clew_returns_zero_for_empty_report(tmp_path):
    # Arrange
    report = verify_cites(
        tmp_path, entries={}, cited_keys=[], resolver=_fake_resolver,
        out=tmp_path / "s.json",
    )
    clew_out = tmp_path / "citations_clew.json"
    # Act
    pushed = push_to_clew(report, out=clew_out)
    # Assert
    assert pushed == 0

# EOF
