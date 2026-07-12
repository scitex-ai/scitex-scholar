"""Tests for scitex_scholar.metadata_engines.individual.ArXivEngine."""

import os

import pytest

vc_arxiv = pytest.importorskip(
    "scitex_scholar.metadata_engines.individual.ArXivEngine"
)
from scitex_scholar.metadata_engines.individual.ArXivEngine import (  # noqa: E402
    ArXivEngine,
)

_SKIP_NETWORK = os.getenv("SCITEX_SCHOLAR_SKIP_NETWORK_TESTS", "1") == "1"
_NETWORK_SKIP_REASON = (
    "live arXiv API call -- run with SCITEX_SCHOLAR_SKIP_NETWORK_TESTS=0 "
    "before any release (scitex-writer, 2026-07-12)"
)


def test_import_ArXivEngine_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a
    missing dependency is reported as a skip, not a pass). The
    single assertion verifies the loaded module's ``__name__``
    matches the requested dotted path — catches accidental aliasing
    and packaging-path drift, which a bare import does not.
    """
    # Arrange
    name = "scitex_scholar.metadata_engines.individual.ArXivEngine"
    # Act
    mod = pytest.importorskip(name)
    # Assert
    assert mod.__name__ == name


@pytest.mark.skipif(_SKIP_NETWORK, reason=_NETWORK_SKIP_REASON)
class TestSearchByDoiLiveNetwork:
    """Regression: `search_query=id:"..."` is not arXiv's exact-ID lookup --
    it silently returns zero entries (verified live against the raw API),
    so every DOI-form arXiv citation fell through to the not-found fallback
    (title=None) and could never classify VERIFIED downstream in
    verify-cites. Fixed to use `id_list`, arXiv's documented direct-fetch
    parameter. Reported by scitex-writer building a citation-trustworthiness
    check, 2026-07-12."""

    def test_real_arxiv_doi_returns_the_real_title(self):
        # Arrange
        engine = ArXivEngine()
        # Act
        result = engine.search(doi="10.48550/arXiv.1706.03762")
        # Assert
        assert result["basic"]["title"] == "Attention Is All You Need"

    def test_real_arxiv_doi_case_insensitive_prefix(self):
        # Arrange
        engine = ArXivEngine()
        # Act
        result = engine.search(doi="10.48550/arxiv.1706.03762")
        # Assert
        assert result["basic"]["title"] == "Attention Is All You Need"
