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


def _alias_shaped_paper():
    """Simulate the alias: same shape, different class object."""
    real = Paper.from_dict(_paper_dict())

    class FakePaper:
        def __init__(self, src):
            self.metadata = src.metadata

    return FakePaper(real)


class TestLooksLikePaper:
    def test_real_paper_passes_shape_check(self):
        # Arrange
        paper = Paper.from_dict(_paper_dict())
        # Act
        result = _looks_like_paper(paper)
        # Assert
        assert result is True

    def test_rejects_string_input_as_non_paper(self):
        # Arrange
        candidate = "nope"
        # Act
        result = _looks_like_paper(candidate)
        # Assert
        assert result is False

    def test_rejects_none_input_as_non_paper(self):
        # Arrange
        candidate = None
        # Act
        result = _looks_like_paper(candidate)
        # Assert
        assert result is False

    def test_rejects_integer_input_as_non_paper(self):
        # Arrange
        candidate = 42
        # Act
        result = _looks_like_paper(candidate)
        # Assert
        assert result is False

    def test_alias_shaped_object_fails_isinstance_check(self):
        # Arrange
        candidate = _alias_shaped_paper()
        # Act
        result = isinstance(candidate, Paper)
        # Assert
        assert result is False

    def test_alias_shaped_object_passes_duck_type_check(self):
        # Arrange
        candidate = _alias_shaped_paper()
        # Act
        result = _looks_like_paper(candidate)
        # Assert
        assert result is True

    def test_papers_collection_accepts_alias_shaped_object(self):
        # Arrange
        candidate = _alias_shaped_paper()
        # Act
        col = Papers([candidate])  # type: ignore[list-item]
        # Assert
        assert len(col) == 1


class TestPapersCollection:
    def test_collection_accepts_single_real_paper(self):
        # Arrange
        paper = Paper.from_dict(_paper_dict())
        # Act
        col = Papers([paper])
        # Assert
        assert len(col) == 1

    def test_collection_skips_non_paper_garbage_entries(self):
        # Arrange
        garbage = ["nope", 42]
        # Act
        col = Papers(garbage)  # type: ignore[list-item]
        # Assert
        assert len(col) == 0

    def test_collection_accepts_plain_dict_paper(self):
        # Arrange
        data = _paper_dict()
        # Act
        col = Papers([data])
        # Assert
        assert len(col) == 1
