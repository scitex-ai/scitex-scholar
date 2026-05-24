#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/integration/test_pdf_highlight.py
"""Tests for the semantic PDF highlighter module.

Converted from the legacy ``unittest.TestCase`` shape to pytest-style
single-assert tests so STX-TQ001 (no bare ``assert`` was visible
through the ``self.assertX(...)`` indirection) and STX-TQ007 (several
methods packed 2-4 ``self.assertX`` calls into one body) both clear.

Focuses on parts that don't require the Anthropic API:
- colour scheme integrity
- sentence splitter edge cases
- offline (stub) classifier behaviour
- offline label application
"""

from __future__ import annotations

import pytest

from scitex_scholar.pdf_highlight import (
    CATEGORIES,
    COLOR_RGB,
    Block,
    apply_classifications,
)
from scitex_scholar.pdf_highlight._blocks import _split_sentences
from scitex_scholar.pdf_highlight._classifier import classify_stub
from scitex_scholar.pdf_highlight._colors import CATEGORY_LABELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block(idx: int, text: str) -> Block:
    return Block(id=idx, page=0, bbox=(0, 0, 1, 1), text=text)


@pytest.fixture
def two_blocks() -> list[Block]:
    return [
        Block(id=0, page=0, bbox=(0, 0, 1, 1), text="foo"),
        Block(id=1, page=0, bbox=(0, 0, 1, 1), text="bar"),
    ]


# ---------------------------------------------------------------------------
# Colour scheme — every category covered, every channel in [0, 1], distinct.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cat", list(CATEGORIES))
def test_every_category_has_an_rgb_entry(cat):
    # Arrange
    # Act
    rgb = COLOR_RGB.get(cat)
    # Assert
    assert rgb is not None, f"{cat} missing RGB"


@pytest.mark.parametrize("cat", list(CATEGORIES))
def test_every_category_has_a_label_entry(cat):
    # Arrange
    # Act
    label = CATEGORY_LABELS.get(cat)
    # Assert
    assert label is not None, f"{cat} missing label"


def test_rgb_tuples_have_all_channels_within_unit_range():
    # Arrange
    # Act
    out_of_range = [
        (cat, v) for cat, rgb in COLOR_RGB.items() for v in rgb if not 0.0 <= v <= 1.0
    ]
    # Assert
    assert out_of_range == []


def test_category_colours_are_pairwise_distinct():
    # Arrange
    rounded = {cat: tuple(round(x, 3) for x in rgb) for cat, rgb in COLOR_RGB.items()}
    # Act
    duplicate_count = len(rounded) - len(set(rounded.values()))
    # Assert
    assert duplicate_count == 0, f"duplicate colours across categories: {rounded}"


# ---------------------------------------------------------------------------
# Sentence splitter edge cases
# ---------------------------------------------------------------------------


def test_splits_on_period_space_capital_returns_three_sentences():
    # Arrange
    s = "First sentence. Second sentence. Third one."
    # Act
    parts = _split_sentences(s)
    # Assert
    assert parts == ["First sentence.", "Second sentence.", "Third one."]


def test_preserves_abbreviation_with_capitalized_follower_returns_two_parts():
    # Arrange
    s = "As shown in Fig. 2, the trend reverses. Later it stabilises."
    # Act
    parts = _split_sentences(s)
    # Assert — "Fig." should not cause a split; whole first clause stays together.
    assert len(parts) == 2


def test_preserves_abbreviation_with_capitalized_follower_keeps_fig_inside_first_part():
    # Arrange
    s = "As shown in Fig. 2, the trend reverses. Later it stabilises."
    # Act
    parts = _split_sentences(s)
    # Assert
    assert "Fig. 2, the trend reverses." in parts[0]


def test_preserves_eg_keeps_marker_inside_first_part():
    # Arrange
    s = "We tested several methods, e.g. random forests. The best was GBM."
    # Act
    parts = _split_sentences(s)
    # Assert
    assert "e.g." in parts[0]


def test_preserves_eg_returns_two_parts():
    # Arrange
    s = "We tested several methods, e.g. random forests. The best was GBM."
    # Act
    parts = _split_sentences(s)
    # Assert
    assert len(parts) == 2


def test_preserves_et_al_keeps_marker_inside_some_part():
    # Arrange
    s = "Following Smith et al. 2019, we computed H. We found H=0.7."
    # Act
    parts = _split_sentences(s)
    # Assert
    assert any("et al." in p for p in parts)


def test_accepts_numbered_and_quoted_openers_returns_at_least_two_parts():
    # Arrange
    s = 'Methods follow. 1. Extract blocks. "Second step." done'
    # Act
    parts = _split_sentences(s)
    # Assert
    assert len(parts) >= 2


def test_empty_input_returns_empty_list():
    # Arrange
    # Act
    parts = _split_sentences("")
    # Assert
    assert parts == []


def test_whitespace_only_input_returns_empty_list():
    # Arrange
    # Act
    parts = _split_sentences("   ")
    # Assert
    assert parts == []


# ---------------------------------------------------------------------------
# Stub classifier — marker recognition
# ---------------------------------------------------------------------------


def test_detects_focal_claim_marker_we_demonstrated():
    # Arrange
    blocks = [_block(0, "We demonstrated that X holds.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "focal_claim"


def test_detects_focal_claim_marker_our_results_show():
    # Arrange
    blocks = [_block(0, "Our results show a clear trend.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "focal_claim"


def test_unmarked_block_is_left_uncategorised():
    # Arrange
    blocks = [_block(0, "The weather was nice.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category is None


def test_detects_focal_limitation_marker_a_limitation():
    # Arrange
    blocks = [_block(0, "A limitation of this study is sample size.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "focal_limitation"


def test_detects_focal_method_marker_we_propose():
    # Arrange
    blocks = [_block(0, "We propose a new method based on wavelets.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "focal_method"


def test_detects_related_supportive_marker_consistent_with():
    # Arrange
    blocks = [_block(0, "This is consistent with Smith (2019).")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "related_supportive"


def test_detects_related_contradictive_marker_in_contrast():
    # Arrange
    blocks = [_block(0, "In contrast to prior work, we found Y.")]
    # Act
    classify_stub(blocks)
    # Assert
    assert blocks[0].category == "related_contradictive"


# ---------------------------------------------------------------------------
# apply_classifications — known/unknown categories and ids
# ---------------------------------------------------------------------------


def test_applies_known_categories_returns_count_of_applied(two_blocks):
    # Arrange
    payload = [
        {"id": 0, "category": "focal_claim", "confidence": 0.9},
        {"id": 1, "category": "focal_method", "confidence": 0.7},
    ]
    # Act
    n = apply_classifications(two_blocks, payload)
    # Assert
    assert n == 2


def test_applies_known_categories_sets_first_block_category(two_blocks):
    # Arrange
    payload = [
        {"id": 0, "category": "focal_claim", "confidence": 0.9},
        {"id": 1, "category": "focal_method", "confidence": 0.7},
    ]
    # Act
    apply_classifications(two_blocks, payload)
    # Assert
    assert two_blocks[0].category == "focal_claim"


def test_applies_known_categories_sets_first_block_confidence(two_blocks):
    # Arrange
    payload = [
        {"id": 0, "category": "focal_claim", "confidence": 0.9},
        {"id": 1, "category": "focal_method", "confidence": 0.7},
    ]
    # Act
    apply_classifications(two_blocks, payload)
    # Assert
    assert two_blocks[0].confidence == 0.9


def test_applies_known_categories_sets_second_block_category(two_blocks):
    # Arrange
    payload = [
        {"id": 0, "category": "focal_claim", "confidence": 0.9},
        {"id": 1, "category": "focal_method", "confidence": 0.7},
    ]
    # Act
    apply_classifications(two_blocks, payload)
    # Assert
    assert two_blocks[1].category == "focal_method"


def test_drops_unknown_categories_returns_zero(two_blocks):
    # Arrange
    payload = [{"id": 0, "category": "nonsense", "confidence": 0.9}]
    # Act
    n = apply_classifications(two_blocks, payload)
    # Assert
    assert n == 0


def test_drops_unknown_categories_leaves_block_category_unset(two_blocks):
    # Arrange
    payload = [{"id": 0, "category": "nonsense", "confidence": 0.9}]
    # Act
    apply_classifications(two_blocks, payload)
    # Assert
    assert two_blocks[0].category is None


def test_ignores_unknown_ids_returns_zero(two_blocks):
    # Arrange
    payload = [{"id": 99, "category": "focal_claim", "confidence": 0.9}]
    # Act
    n = apply_classifications(two_blocks, payload)
    # Assert
    assert n == 0
