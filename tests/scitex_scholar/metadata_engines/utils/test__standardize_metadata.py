"""Regression tests for JATS/HTML sanitization in `standardize_metadata`.

scitex-hub (a downstream webapp) reported that raw JATS/HTML markup from
CrossRef-style source data (e.g. ``<jats:p>``, ``<scp>CA1</scp>``,
``<jats:title>``) leaked through `basic.title` / `basic.abstract` into the
visitor-facing UI. `standardize_metadata()` is the single choke point every
metadata engine funnels its result through, so it must sanitize those
free-text fields before returning.
"""

from __future__ import annotations

from scitex_scholar.metadata_engines.utils._standardize_metadata import (
    standardize_metadata,
)


class TestStandardizeMetadataSanitizesFreeText:
    def test_strips_jats_p_from_abstract(self):
        # Arrange
        metadata = {
            "basic": {
                "abstract": "<jats:p>Hippocampal recordings in <scp>CA1</scp>.</jats:p>",
            },
        }
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["abstract"] == "Hippocampal recordings in CA1."

    def test_strips_jats_title_tag_from_title(self):
        # Arrange
        metadata = {
            "basic": {
                "title": "<jats:title>Seizure detection in <scp>CA1</scp></jats:title>",
            },
        }
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["title"] == "Seizure detection in CA1"

    def test_sanitized_abstract_has_no_angle_brackets(self):
        # Arrange
        metadata = {
            "basic": {
                "abstract": (
                    "<jats:p>Background: <jats:italic>in vitro</jats:italic> "
                    "recordings from <scp>CA1</scp> pyramidal neurons.</jats:p>"
                ),
            },
        }
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert "<" not in result["basic"]["abstract"]

    def test_none_title_passes_through_untouched(self):
        # Arrange
        metadata = {"basic": {"title": None}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["title"] is None

    def test_none_abstract_passes_through_untouched(self):
        # Arrange
        metadata = {"basic": {"abstract": None}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["abstract"] is None

    def test_non_string_year_passes_through_untouched(self):
        # Arrange
        metadata = {"basic": {"year": 2023}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["year"] == 2023

    def test_authors_list_passes_through_untouched(self):
        # Arrange
        metadata = {"basic": {"authors": ["Jane Doe", "John Smith"]}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["authors"] == ["Jane Doe", "John Smith"]

    def test_doi_field_passes_through_untouched(self):
        # Arrange
        metadata = {"id": {"doi": "10.1000/<not-a-real-tag>"}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["id"]["doi"] == "10.1000/<not-a-real-tag>"

    def test_clean_title_without_tags_is_unchanged(self):
        # Arrange
        metadata = {"basic": {"title": "A clean title with no markup"}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["basic"]["title"] == "A clean title with no markup"

    def test_missing_basic_section_does_not_raise(self):
        # Arrange
        metadata = {"id": {"doi": "10.1000/xyz"}}
        # Act
        result = standardize_metadata(metadata)
        # Assert
        assert result["id"]["doi"] == "10.1000/xyz"


# EOF
