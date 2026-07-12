"""Behavioral tests for scitex_scholar.storage._mixins._symlink_handlers."""

import pytest


def test_import__symlink_handlers_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a
    missing dependency is reported as a skip, not a pass). The
    single assertion verifies the loaded module's ``__name__``
    matches the requested dotted path — catches accidental aliasing
    and packaging-path drift, which a bare import does not.
    """
    # Arrange
    name = "scitex_scholar.storage._mixins._symlink_handlers"
    # Act
    mod = pytest.importorskip(name)
    # Assert
    assert mod.__name__ == name


from scitex_scholar.storage._mixins._symlink_handlers import SymlinkHandlersMixin


class _FakeConfig:
    """Real (non-mock) stand-in exposing the single attribute the mixin reads."""

    def __init__(self, path_manager):
        self.path_manager = path_manager


class _Host(SymlinkHandlersMixin):
    """Minimal real host combining the mixin with the config surface it needs."""

    def __init__(self, path_manager):
        self.config = _FakeConfig(path_manager)


class TestGenerateReadableNameJournalSanitization:
    """Regression: journal-name sanitization must not crash (#scholar-ai-for-science).

    ``_generate_readable_name`` previously called
    ``path_manager._sanitize_filename(...)`` as if it were a bound method;
    ``_sanitize_filename`` is only ever a module-level helper in
    ``_path_helpers.py``, so every symlink update with a non-empty journal
    name raised ``AttributeError`` and silently skipped the project link.
    """

    def test_generate_readable_name_with_journal_does_not_raise(self, tmp_path):
        # Arrange
        from scitex_scholar.config.core._PathManager import PathManager

        host = _Host(PathManager(scholar_dir=tmp_path))
        # Act
        name = host._generate_readable_name(
            comprehensive_metadata={},
            master_storage_path=tmp_path,
            authors=["Jane Doe"],
            year=2026,
            journal="Front. Neurosci",
        )
        # Assert
        assert "Front-Neurosci" in name

    def test_generate_readable_name_sanitizes_dots_and_spaces_in_journal(
        self, tmp_path
    ):
        # Arrange
        from scitex_scholar.config.core._PathManager import PathManager

        host = _Host(PathManager(scholar_dir=tmp_path))
        # Act
        name = host._generate_readable_name(
            comprehensive_metadata={},
            master_storage_path=tmp_path,
            authors=["Jane Doe"],
            year=2026,
            journal="IEEE J. Biomed. Health Inform",
        )
        # Assert
        assert "IEEE-J-Biomed-Health-Inform" in name

    def test_generate_readable_name_falls_back_to_unknown_without_journal(
        self, tmp_path
    ):
        # Arrange
        from scitex_scholar.config.core._PathManager import PathManager

        host = _Host(PathManager(scholar_dir=tmp_path))
        # Act
        name = host._generate_readable_name(
            comprehensive_metadata={},
            master_storage_path=tmp_path,
            authors=["Jane Doe"],
            year=2026,
            journal=None,
        )
        # Assert
        assert "Unknown" in name

# EOF
