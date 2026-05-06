"""Regression tests for `scitex_scholar.clean_abstract` (#142)."""

from __future__ import annotations

import scitex_scholar


class TestCleanAbstract:
    def test_strips_jats_p(self):
        assert (
            scitex_scholar.clean_abstract("<jats:p>Hello world.</jats:p>")
            == "Hello world."
        )

    def test_strips_jats_italic(self):
        assert (
            scitex_scholar.clean_abstract(
                "<jats:p>See <jats:italic>in vitro</jats:italic> data.</jats:p>"
            )
            == "See in vitro data."
        )

    def test_strips_plain_html(self):
        assert scitex_scholar.clean_abstract("<p>A <i>b</i> c.</p>") == "A b c."

    def test_decodes_html_entities(self):
        assert scitex_scholar.clean_abstract("AMP&amp;DEF &lt;ok&gt;") == "AMP&DEF <ok>"

    def test_empty_input(self):
        assert scitex_scholar.clean_abstract("") == ""

    def test_normalizes_whitespace(self):
        # Tags removed leaves double-spaces; function should collapse.
        assert scitex_scholar.clean_abstract("<p>a</p>   <p>b</p>") == "a b"


# EOF
