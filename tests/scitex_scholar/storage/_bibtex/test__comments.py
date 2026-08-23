#!/usr/bin/env python3
# File: tests/scitex_scholar/storage/_bibtex/test__comments.py
"""Regression tests for BibTeX ``%`` comment sanitization.

A raw ``@`` in a ``%`` header line is read by BibTeX parsers as the start of an
entry (they scan for ``@`` and do not honour ``%``), which aborts the parse of
an otherwise valid file. These tests pin that behaviour down.
"""

from __future__ import annotations

from scitex_scholar.storage._bibtex import (
    BIBTEX_AT_REPLACEMENT,
    sanitize_bibtex_comments,
)


class TestCommentLinesAreSanitized:
    """``@`` must not survive inside a ``%`` comment line."""

    def test_at_in_comment_line_is_replaced(self):
        # Arrange
        content = "% Source: lab@uni.edu.bib"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert "@" not in result

    def test_at_in_comment_line_is_replaced_with_placeholder(self):
        # Arrange
        content = "% Source: lab@uni.edu.bib"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert result == f"% Source: lab{BIBTEX_AT_REPLACEMENT}uni.edu.bib"

    def test_every_at_in_a_comment_line_is_replaced(self):
        # Arrange
        content = "%   1. a@b.bib and c@d.bib"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert result.count(BIBTEX_AT_REPLACEMENT) == 2

    def test_indented_comment_line_is_sanitized(self):
        # Arrange
        content = "    % indented a@b"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert "@" not in result


class TestEntriesArePreserved:
    """Sanitization must never touch the BibTeX entries themselves."""

    def test_entry_line_keeps_its_at_sigil(self):
        # Arrange
        content = "% header\n@article{key,"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert result.split("\n")[1] == "@article{key,"

    def test_at_inside_a_field_value_is_preserved(self):
        # Arrange
        content = "@article{key,\n  author = {a@b.com},\n}"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert "a@b.com" in result

    def test_content_without_comments_is_unchanged(self):
        # Arrange
        content = "@article{key,\n  title = {No comments here},\n}"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert result == content

    def test_line_count_is_preserved(self):
        # Arrange
        content = "% a@b\n@article{key,\n  title = {T},\n}\n"
        # Act
        result = sanitize_bibtex_comments(content)
        # Assert
        assert len(result.split("\n")) == len(content.split("\n"))


# EOF
