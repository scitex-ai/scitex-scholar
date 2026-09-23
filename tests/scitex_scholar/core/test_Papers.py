#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Papers collection accepts Papers reached via import aliases.

Regression: the umbrella ``scitex`` package registers ``scitex.scholar.*``
as lazy aliases of ``scitex_scholar.*``; the import system can materialize
the same Paper class under two module identities, defeating ``isinstance``.
Merges then silently produced header-only .bib files.
"""

from scitex_scholar.core.Paper import Paper
from scitex_scholar.core.Papers import Papers, _looks_like_paper


def _paper_dict(title="Attention Is All You Need"):
    return {
        "title": title,
        "authors": ["Vaswani, Ashish"],
        "year": 2017,
        "doi": "10.48550/arXiv.1706.03762",
    }


class TestLooksLikePaper:
    def test_real_paper_passes(self):
        assert _looks_like_paper(Paper.from_dict(_paper_dict())) is True

    def test_non_paper_rejected(self):
        assert _looks_like_paper("nope") is False
        assert _looks_like_paper(None) is False
        assert _looks_like_paper(42) is False

    def test_alias_class_identity_not_required(self):
        """Simulate the alias: same shape, different class object."""
        real = Paper.from_dict(_paper_dict())

        class FakePaper:
            def __init__(self, src):
                self.metadata = src.metadata

        assert isinstance(FakePaper(real), Paper) is False
        assert _looks_like_paper(FakePaper(real)) is True
        assert len(Papers([FakePaper(real)])) == 1  # type: ignore[list-item]


class TestPapersCollection:
    def test_accepts_papers(self):
        col = Papers([Paper.from_dict(_paper_dict())])
        assert len(col) == 1

    def test_skips_garbage(self):
        col = Papers(["nope", 42])  # type: ignore[list-item]
        assert len(col) == 0

    def test_accepts_dicts(self):
        col = Papers([_paper_dict()])
        assert len(col) == 1
