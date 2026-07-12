#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__resolve.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._resolve."""
from __future__ import annotations

import os

import pytest

vc_resolve = pytest.importorskip("scitex_scholar.verify_cites._resolve")
from scitex_scholar.verify_cites._resolve import (  # noqa: E402
    ResolvedRef,
    _authors_list,
    _std,
    default_resolver,
)

_SKIP_NETWORK = os.getenv("SCITEX_SCHOLAR_SKIP_NETWORK_TESTS", "1") == "1"
_NETWORK_SKIP_REASON = (
    "live CrossRef network call -- run with SCITEX_SCHOLAR_SKIP_NETWORK_TESTS=0 "
    "before any release; this is the end-to-end check that a real DOI actually "
    "reaches VERIFIED and a fabricated title reaches no-hit, not just the "
    "injected-resolver unit tests above (scitex-writer, 2026-07-12)"
)


def test_authors_list_splits_on_and():
    # Arrange
    raw = "Jane Doe and John Smith and A. B. Carter"
    # Act
    authors = _authors_list({"author": raw})
    # Assert
    assert authors == ["Jane Doe", "John Smith", "A. B. Carter"]


def test_authors_list_empty_without_author_field():
    # Arrange
    # Act
    authors = _authors_list({})
    # Assert
    assert authors == []


def test_std_returns_none_for_empty_metadata():
    # Arrange
    # Act
    resolved = _std(None, "crossref")
    # Assert
    assert resolved is None


class TestStdReadsRealEngineNestedShape:
    """Regression: metadata engines return {"id": {"doi": ...}, "basic":
    {"title": ...}} (see _BaseDOIEngine._extract_metadata_from_item /
    _create_minimal_metadata), NOT flat {"title": ..., "doi": ...}. _std()
    reading the flat shape meant resolved.title was always None, so
    classify() could never reach VERIFIED via any online engine (reported
    by scitex-writer as a sim=0.0 "hit" on a fabricated citation)."""

    def test_std_extracts_nested_basic_title_and_id_doi(self):
        # Arrange
        meta = {"id": {"doi": "10.1/x"}, "basic": {"title": "T"}}
        # Act
        resolved = _std(meta, "crossref")
        # Assert
        assert resolved == ResolvedRef(title="T", doi="10.1/x", source="crossref")

    def test_std_falls_back_to_external_ids_doi(self):
        # Arrange
        meta = {"basic": {"title": "T"}, "externalIds": {"DOI": "10.1/y"}}
        # Act
        resolved = _std(meta, "crossref")
        # Assert
        assert resolved.doi == "10.1/y"


class TestStdRejectsEchoedMissWithoutDoi:
    """Regression: CrossRef/OpenAlex/ArXiv's not-found fallback echoes the
    query's own title back into basic.title with no id.doi -- structurally
    identical to a genuine hit unless a DOI is also required. This is the
    exact shape scitex-writer's fabricated-citation report surfaced as a
    sim=0.0 "hit"; without this guard, fixing the nested-key bug alone
    would turn it into a false sim=1.0 self-match VERIFIED instead."""

    @pytest.mark.parametrize("source", ["crossref", "openalex", "arxiv"])
    def test_rejects_title_without_doi(self, source):
        # Arrange
        meta = {"id": {"doi": None}, "basic": {"title": "Echoed Query Title"}}
        # Act
        resolved = _std(meta, source)
        # Assert
        assert resolved is None

    def test_semantic_scholar_corpus_id_accepts_doi_less_title(self):
        """Semantic Scholar's CorpusId lookup returns bare None on a miss
        (never reaches the echo shape), so a title without a DOI there is
        genuinely DOI-less-but-real -- must not be rejected by the guard
        above."""
        # Arrange
        meta = {"id": {"doi": None}, "basic": {"title": "Real DOI-less Paper"}}
        # Act
        resolved = _std(meta, "semantic_scholar")
        # Assert
        assert resolved == ResolvedRef(
            title="Real DOI-less Paper", doi=None, source="semantic_scholar"
        )


def test_default_resolver_offline_short_circuits_without_network():
    # Arrange
    entry = {"title": "Anything", "doi": "10.1/x"}
    # Act
    resolved = default_resolver(entry, offline=True)
    # Assert
    assert resolved is None


@pytest.mark.skipif(_SKIP_NETWORK, reason=_NETWORK_SKIP_REASON)
class TestDefaultResolverLiveNetwork:
    """End-to-end pin against the real CrossRef/OpenAlex/ArXiv APIs -- the
    injected-resolver tests above cannot catch a bug in _std()'s parsing of
    the real engines' response shape (which is exactly how the never-VERIFIED
    bug shipped in the first place). Skipped by default (network + external
    service dependency); run explicitly before any release."""

    def test_real_doi_resolves_and_classifies_verified(self):
        # Arrange
        from scitex_scholar.verify_cites._classify import classify

        entry = {
            "title": "CircStat: A MATLAB Toolbox for Circular Statistics",
            "doi": "10.18637/jss.v031.i10",
        }
        # Act
        resolved = default_resolver(entry)
        status = classify("Berens2009", entry, resolved, min_confidence=0.6)
        # Assert
        assert status.status == "verified"

    def test_fabricated_title_resolves_to_no_hit(self):
        # Arrange
        entry = {
            "title": "A Totally Fabricated Paper About Nonexistent Neural Widgets 9876",
            "author": "Nobody Fakename",
        }
        # Act
        resolved = default_resolver(entry)
        # Assert
        assert resolved is None

    def test_arxiv_doi_resolves_and_classifies_verified(self):
        """Regression: ArXivEngine._search_by_doi used the wrong arXiv API
        query field, so DOI-form arXiv citations -- the single most common
        citation form in ML/CS manuscripts -- never verified (reported by
        scitex-writer, 2026-07-12)."""
        # Arrange
        from scitex_scholar.verify_cites._classify import classify

        entry = {
            "title": "Attention Is All You Need",
            "doi": "10.48550/arXiv.1706.03762",
        }
        # Act
        resolved = default_resolver(entry)
        status = classify("Vaswani2017", entry, resolved, min_confidence=0.6)
        # Assert
        assert status.status == "verified"

    def test_bare_arxiv_eprint_resolves_and_classifies_verified(self):
        # Arrange
        from scitex_scholar.verify_cites._classify import classify

        entry = {"title": "Attention Is All You Need", "eprint": "1706.03762"}
        # Act
        resolved = default_resolver(entry)
        status = classify("Vaswani2017b", entry, resolved, min_confidence=0.6)
        # Assert
        assert status.status == "verified"

# EOF
