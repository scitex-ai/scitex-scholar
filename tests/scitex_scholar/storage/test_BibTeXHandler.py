#!/usr/bin/env python3
# File: tests/scitex_scholar/storage/test_BibTeXHandler.py
"""Tests for the composed BibTeXHandler class."""

from __future__ import annotations

from pathlib import Path

from scitex_scholar.storage import BibTeXHandler


class TestComposedSurface:
    """The mixin split must not drop any method off the public class."""

    def test_parsing_method_resolves(self):
        # Arrange
        handler = BibTeXHandler()
        # Act
        method = getattr(handler, "papers_from_bibtex", None)
        # Assert
        assert callable(method)

    def test_writing_method_resolves(self):
        # Arrange
        handler = BibTeXHandler()
        # Act
        method = getattr(handler, "papers_to_bibtex", None)
        # Assert
        assert callable(method)

    def test_merging_method_resolves(self):
        # Arrange
        handler = BibTeXHandler()
        # Act
        method = getattr(handler, "merge_bibtex_files", None)
        # Assert
        assert callable(method)

    def test_projects_method_resolves(self):
        # Arrange
        handler = BibTeXHandler()
        # Act
        method = getattr(handler, "export_project_bibliography", None)
        # Assert
        assert callable(method)

    def test_project_is_stored(self):
        # Arrange
        handler = BibTeXHandler(project="demo")
        # Act
        project = handler.project
        # Assert
        assert project == "demo"


class TestHeaderCommentsAreParseable:
    """An ``@``-bearing source filename must not corrupt the emitted header.

    Regression: a raw ``@`` in a ``%`` header line is parsed as the start of a
    BibTeX entry, which breaks the whole file (seen downstream in a merged
    bibliography).
    """

    def test_at_bearing_source_filename_leaves_no_bare_at_in_header(self, tmp_path):
        # Arrange
        handler = BibTeXHandler()
        out = tmp_path / "merged.bib"
        # Act
        content = handler.papers_to_bibtex_with_sources(
            [], out, source_files=[Path("lab@uni.bib")]
        )
        # Assert
        assert "@" not in content

    def test_written_file_matches_returned_content(self, tmp_path):
        # Arrange
        handler = BibTeXHandler()
        out = tmp_path / "merged.bib"
        # Act
        content = handler.papers_to_bibtex_with_sources(
            [], out, source_files=[Path("lab@uni.bib")]
        )
        # Assert
        assert out.read_text() == content


# EOF
