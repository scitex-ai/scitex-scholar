#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/verify_cites/test__resolve.py
# ----------------------------------------
"""Unit tests for scitex_scholar.verify_cites._resolve."""

from __future__ import annotations

import http.server
import json
import os
import threading

import pytest

vc_resolve = pytest.importorskip("scitex_scholar.verify_cites._resolve")
from scitex_scholar.verify_cites._resolve import (  # noqa: E402
    LookupFailed,
    ResolvedRef,
    _authors_list,
    _lookup,
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

    def test_rejects_doi_echo_without_title(self):
        """Regression: a DOI lookup that FAILED (429, 5xx, timeout) makes
        CrossRef/OpenAlex fall back to _create_minimal_metadata(doi=<query>),
        which echoes the queried DOI with no title. Accepting that as a hit
        produced a sim=0.0 "hit but weak title match" verdict for a lookup
        that never happened."""
        # Arrange
        meta = {"id": {"doi": "10.1/queried"}, "basic": {"title": None}}
        # Act
        resolved = _std(meta, "crossref")
        # Assert
        assert resolved is None


# ---------------------------------------------------------------------------
# Transport failures vs. genuine misses, over REAL HTTP on loopback.
#
# A stdlib HTTP server stands in for the metadata service at the HTTP boundary
# only; the real CrossRef/OpenAlex engines (requests, raise_for_status, their
# not-found fallback) run unmodified against it.
# ---------------------------------------------------------------------------


class _Service:
    """Loopback HTTP server answering every GET with a fixed status/body."""

    def __init__(self, status, body=None):
        self.status = status
        self.body = body if body is not None else {}
        self.hits = 0
        service = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (stdlib hook name)
                service.hits += 1
                payload = json.dumps(service.body).encode()
                self.send_response(service.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/works"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _crossref_at(url):
    from scitex_scholar.metadata_engines.individual.CrossRefEngine import (
        CrossRefEngine,
    )

    engine = CrossRefEngine()
    engine.base_url = url
    return engine


def _openalex_at(url):
    from scitex_scholar.metadata_engines.individual.OpenAlexEngine import (
        OpenAlexEngine,
    )

    engine = OpenAlexEngine()
    engine.base_url = url
    return engine


def _raised(fn, *args, **kwargs):
    """Call ``fn``; return the LookupFailed it raised, else None."""
    try:
        fn(*args, **kwargs)
    except LookupFailed as exc:
        return exc
    return None


class TestLookupSeparatesTransportFailureFromMiss:
    def test_rate_limited_doi_lookup_raises_rate_limited_lookup_failed(self):
        # Arrange
        with _Service(429, {"message": "Too Many Requests"}) as svc:
            engine = _crossref_at(svc.url)
            # Act
            err = _raised(_lookup, engine, "crossref", doi="10.1/x")
        # Assert
        assert isinstance(err, LookupFailed) and err.rate_limited

    def test_rate_limited_failure_names_the_service_and_http_status(self):
        # Arrange
        with _Service(429) as svc:
            engine = _crossref_at(svc.url)
            # Act
            err = _raised(_lookup, engine, "crossref", doi="10.1/x")
        # Assert
        assert "crossref" in str(err) and "429" in str(err)

    @pytest.mark.parametrize("status", [503, 403])
    def test_unanswered_query_raises_lookup_failed_not_rate_limited(self, status):
        # Arrange
        with _Service(status) as svc:
            engine = _crossref_at(svc.url)
            # Act
            err = _raised(_lookup, engine, "crossref", doi="10.1/x")
        # Assert
        assert isinstance(err, LookupFailed) and not err.rate_limited

    def test_unreachable_service_raises_lookup_failed(self):
        # Arrange: bind a port, then close it so nothing is listening.
        with _Service(200) as svc:
            url = svc.url
        engine = _crossref_at(url)
        # Act
        err = _raised(_lookup, engine, "crossref", doi="10.1/x")
        # Assert
        assert isinstance(err, LookupFailed)

    def test_not_found_doi_is_a_plain_miss(self):
        # Arrange
        with _Service(404, {"message": "Resource not found."}) as svc:
            engine = _crossref_at(svc.url)
            # Act
            resolved = _lookup(engine, "crossref", doi="10.1/x")
        # Assert
        assert resolved is None

    def test_found_doi_resolves_with_title(self):
        # Arrange
        body = {"message": {"DOI": "10.1/x", "title": ["A Real Title"]}}
        with _Service(200, body) as svc:
            engine = _crossref_at(svc.url)
            # Act
            resolved = _lookup(engine, "crossref", doi="10.1/x")
        # Assert
        assert (resolved.title, resolved.doi) == ("A Real Title", "10.1/x")


class TestDefaultResolverUnderRateLimit:
    def test_doi_entry_raises_lookup_failed_when_every_service_is_throttled(self):
        # Arrange
        entry = {"title": "A Real Title", "doi": "10.1/x"}
        with _Service(429) as svc:
            engines = {
                "crossref": _crossref_at(svc.url),
                "openalex": _openalex_at(svc.url),
            }
            # Act
            err = _raised(default_resolver, entry, engines=engines)
        # Assert
        assert isinstance(err, LookupFailed) and err.rate_limited

    def test_title_only_entry_raises_lookup_failed_instead_of_no_hit(self):
        """A throttled title search used to return None, which classify()
        turns into HALLUCINATED ("possibly fabricated")."""
        # Arrange
        entry = {"title": "A Real Title", "author": "Jane Doe", "year": "2020"}
        with _Service(429) as svc:
            engines = {
                "crossref": _crossref_at(svc.url),
                "openalex": _openalex_at(svc.url),
            }
            # Act
            err = _raised(default_resolver, entry, engines=engines)
        # Assert
        assert isinstance(err, LookupFailed)

    def test_second_service_answering_wins_over_first_service_throttling(self):
        # Arrange
        entry = {"title": "A Real Title", "doi": "10.1/x"}
        body = {"results": [{"doi": "https://doi.org/10.1/x", "title": "A Real Title"}]}
        with _Service(429) as throttled, _Service(200, body) as healthy:
            engines = {
                "crossref": _crossref_at(throttled.url),
                "openalex": _openalex_at(healthy.url),
            }
            # Act
            resolved = default_resolver(entry, engines=engines)
        # Assert
        assert (resolved.source, resolved.title) == ("openalex", "A Real Title")

    def test_genuine_miss_everywhere_is_none_not_a_failure(self):
        # Arrange
        entry = {"title": "A Real Title", "doi": "10.1/x"}
        with _Service(404) as svc:
            engines = {
                "crossref": _crossref_at(svc.url),
                "openalex": _openalex_at(svc.url),
            }
            # Act
            resolved = default_resolver(entry, engines=engines)
        # Assert
        assert resolved is None


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

    def test_bare_arxiv_eprint_resolves_deterministically_via_arxiv_engine(self):
        """Regression: a bare `eprint` (no doi) used to be checked only as a
        boolean gate, then thrown away -- ArXivEngine.search() was called
        with doi=None, falling through to keyword-based title search. For a
        short, common-word title ("Attention Is All You Need" -> just
        "attention"/"need"), that search can legitimately miss the real
        paper among its top-N results and fall through further to an
        unreliable CrossRef title-search fallback (non-deterministic:
        verified in one run, unverified in another -- reported by
        scitex-writer, 2026-07-12). Canonicalizing eprint to an arXiv DOI
        routes it through the deterministic id_list lookup instead."""
        # Arrange
        from scitex_scholar.verify_cites._classify import classify

        entry = {"title": "Attention Is All You Need", "eprint": "1706.03762"}
        # Act
        resolved = default_resolver(entry)
        status = classify("Vaswani2017b", entry, resolved, min_confidence=0.6)
        # Assert
        assert resolved.source == "arxiv" and status.status == "verified"

    def test_title_only_entry_caps_at_unverified_even_with_a_real_matchable_title(self):
        """Regression: an identifier-less entry that reaches step 4 (title/
        author/year fuzzy search) and genuinely matches must still cap at
        UNVERIFIED, never VERIFIED -- CrossRef/OpenAlex's title index is not
        guaranteed stable across identical queries, so this path is the one
        scitex-writer flagged as reachable by ANY title-only citation and
        asked to be treated as non-deterministic evidence (2026-07-12)."""
        # Arrange
        from scitex_scholar.verify_cites._classify import classify

        entry = {"title": "CircStat: A MATLAB Toolbox for Circular Statistics"}
        # Act
        resolved = default_resolver(entry)
        status = classify("Berens2009e", entry, resolved, min_confidence=0.6)
        # Assert
        assert status.status != "verified"


# EOF
