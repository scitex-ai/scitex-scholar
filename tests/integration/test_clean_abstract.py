"""Regression tests for `scitex_scholar.clean_abstract` (#142)."""

from __future__ import annotations

import scitex_scholar


class TestCleanAbstract:
    def test_strips_jats_p(self):
        # Arrange
        # Act
        # Assert
        assert (
            scitex_scholar.clean_abstract("<jats:p>Hello world.</jats:p>")
            == "Hello world."
        )

    def test_strips_jats_italic(self):
        # Arrange
        # Act
        # Assert
        assert (
            scitex_scholar.clean_abstract(
                "<jats:p>See <jats:italic>in vitro</jats:italic> data.</jats:p>"
            )
            == "See in vitro data."
        )

    def test_strips_plain_html(self):
        # Arrange
        # Act
        # Assert
        assert scitex_scholar.clean_abstract("<p>A <i>b</i> c.</p>") == "A b c."

    def test_decodes_html_entities(self):
        # Arrange
        # Act
        # Assert
        assert scitex_scholar.clean_abstract("AMP&amp;DEF &lt;ok&gt;") == "AMP&DEF <ok>"

    def test_empty_input_scitex_scholar_clean_abstract(self):
        # Arrange
        # Act
        # Assert
        assert scitex_scholar.clean_abstract("") == ""

    def test_normalizes_whitespace_scitex_scholar_clean_abstract_p_a_p_p_b_p_a_b(self):
        # Tags removed leaves double-spaces; function should collapse.
        # Arrange
        # Act
        # Assert
        assert scitex_scholar.clean_abstract("<p>a</p>   <p>b</p>") == "a b"


# EOF
