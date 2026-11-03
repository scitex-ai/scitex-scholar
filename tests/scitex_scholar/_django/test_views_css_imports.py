"""Stylesheet inventory follows the URLs actually served by the leaf."""

import pytest

from tests.scitex_scholar._django.test_views import _declared, _resolve_css


def test_import_query_and_fragment_reach_the_actual_stylesheet(tmp_path):
    # Arrange — cache versions belong to the URL, not the local filename.
    (tmp_path / "tokens.css").write_text(":root { --owned-token: 85px; }")
    entry = tmp_path / "entry.css"
    entry.write_text('@import url("tokens.css?v=04fbccf491ea#theme");')
    # Act
    declared = _declared(_resolve_css(entry))
    # Assert
    assert "--owned-token" in declared


def test_percent_encoded_import_resolves_its_local_filename(tmp_path):
    # Arrange
    (tmp_path / "named tokens.css").write_text(":root { --encoded-token: 14px; }")
    entry = tmp_path / "entry.css"
    entry.write_text('@import url("named%20tokens.css?v=2");')
    # Act
    declared = _declared(_resolve_css(entry))
    # Assert
    assert "--encoded-token" in declared


def test_missing_local_import_fails_instead_of_hiding_tokens(tmp_path):
    # Arrange
    entry = tmp_path / "entry.css"
    entry.write_text('@import url("deleted.css?v=3");')
    # Act
    def resolve():
        return _resolve_css(entry)
    # Assert
    with pytest.raises(FileNotFoundError):
        resolve()
