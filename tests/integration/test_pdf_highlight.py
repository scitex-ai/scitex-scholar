#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: tests/scitex_scholar/test_pdf_highlight.py
"""Tests for the semantic PDF highlighter module.

Focuses on parts that don't require the Anthropic API:
- colour scheme integrity
- sentence splitter edge cases
- offline (stub) classifier behaviour
- offline label application
"""

import unittest

from scitex_scholar.pdf_highlight import (
    CATEGORIES,
    COLOR_RGB,
    Block,
    apply_classifications,
)
from scitex_scholar.pdf_highlight._blocks import _split_sentences
from scitex_scholar.pdf_highlight._classifier import classify_stub
from scitex_scholar.pdf_highlight._colors import CATEGORY_LABELS


class TestColors(unittest.TestCase):
    def test_every_category_has_an_rgb_and_a_label(self):
        for cat in CATEGORIES:
            self.assertIn(cat, COLOR_RGB, f"{cat} missing RGB")
            self.assertIn(cat, CATEGORY_LABELS, f"{cat} missing label")

    def test_rgb_tuples_are_in_unit_range(self):
        for cat, (r, g, b) in COLOR_RGB.items():
            for v in (r, g, b):
                self.assertGreaterEqual(v, 0.0, f"{cat} has negative channel")
                self.assertLessEqual(v, 1.0, f"{cat} has channel > 1.0")

    def test_colours_are_distinct(self):
        seen = set()
        for cat, rgb in COLOR_RGB.items():
            rounded = tuple(round(x, 3) for x in rgb)
            self.assertNotIn(
                rounded, seen, f"{cat} shares colour with another category"
            )
            seen.add(rounded)


class TestSentenceSplitter(unittest.TestCase):
    def test_splits_on_period_space_capital(self):
        s = "First sentence. Second sentence. Third one."
        self.assertEqual(
            _split_sentences(s), ["First sentence.", "Second sentence.", "Third one."]
        )

    def test_preserves_abbreviation_with_capitalized_follower(self):
        s = "As shown in Fig. 2, the trend reverses. Later it stabilises."
        parts = _split_sentences(s)
        # "Fig." should not cause a split; whole first clause stays together.
        self.assertEqual(len(parts), 2)
        self.assertIn("Fig.", parts[0])
        self.assertIn("2, the trend reverses.", parts[0])

    def test_preserves_eg_ie(self):
        s = "We tested several methods, e.g. random forests. The best was GBM."
        parts = _split_sentences(s)
        self.assertEqual(len(parts), 2)
        self.assertIn("e.g.", parts[0])

    def test_preserves_et_al(self):
        s = "Following Smith et al. 2019, we computed H. We found H=0.7."
        parts = _split_sentences(s)
        self.assertTrue(any("et al." in p for p in parts))

    def test_accepts_numbered_and_quoted_openers(self):
        s = 'Methods follow. 1. Extract blocks. "Second step." done'
        parts = _split_sentences(s)
        self.assertGreaterEqual(len(parts), 2)

    def test_empty_and_whitespace_input(self):
        self.assertEqual(_split_sentences(""), [])
        self.assertEqual(_split_sentences("   "), [])


class TestStubClassifier(unittest.TestCase):
    def _block(self, idx: int, text: str) -> Block:
        return Block(id=idx, page=0, bbox=(0, 0, 1, 1), text=text)

    def test_detects_claim_markers(self):
        blocks = [
            self._block(0, "We demonstrated that X holds."),
            self._block(1, "Our results show a clear trend."),
            self._block(2, "The weather was nice."),
        ]
        classify_stub(blocks)
        self.assertEqual(blocks[0].category, "focal_claim")
        self.assertEqual(blocks[1].category, "focal_claim")
        self.assertIsNone(blocks[2].category)

    def test_detects_limitation_markers(self):
        blocks = [self._block(0, "A limitation of this study is sample size.")]
        classify_stub(blocks)
        self.assertEqual(blocks[0].category, "focal_limitation")

    def test_detects_method_markers(self):
        blocks = [self._block(0, "We propose a new method based on wavelets.")]
        classify_stub(blocks)
        self.assertEqual(blocks[0].category, "focal_method")

    def test_detects_supportive_and_contradictive_markers(self):
        s_blocks = [self._block(0, "This is consistent with Smith (2019).")]
        classify_stub(s_blocks)
        self.assertEqual(s_blocks[0].category, "related_supportive")

        c_blocks = [self._block(0, "In contrast to prior work, we found Y.")]
        classify_stub(c_blocks)
        self.assertEqual(c_blocks[0].category, "related_contradictive")


class TestApplyClassifications(unittest.TestCase):
    def _blocks(self) -> list[Block]:
        return [
            Block(id=0, page=0, bbox=(0, 0, 1, 1), text="foo"),
            Block(id=1, page=0, bbox=(0, 0, 1, 1), text="bar"),
        ]

    def test_applies_known_categories(self):
        blocks = self._blocks()
        n = apply_classifications(
            blocks,
            [
                {"id": 0, "category": "focal_claim", "confidence": 0.9},
                {"id": 1, "category": "focal_method", "confidence": 0.7},
            ],
        )
        self.assertEqual(n, 2)
        self.assertEqual(blocks[0].category, "focal_claim")
        self.assertEqual(blocks[0].confidence, 0.9)
        self.assertEqual(blocks[1].category, "focal_method")

    def test_drops_unknown_categories(self):
        blocks = self._blocks()
        n = apply_classifications(
            blocks,
            [
                {"id": 0, "category": "nonsense", "confidence": 0.9},
            ],
        )
        self.assertEqual(n, 0)
        self.assertIsNone(blocks[0].category)

    def test_ignores_unknown_ids(self):
        blocks = self._blocks()
        n = apply_classifications(
            blocks,
            [
                {"id": 99, "category": "focal_claim", "confidence": 0.9},
            ],
        )
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
