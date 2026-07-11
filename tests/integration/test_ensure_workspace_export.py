"""Regression test: ensure_workspace must be a top-level public function (#scholar-export-ensure-workspace)."""

import inspect

import scitex_scholar


class TestEnsureWorkspaceTopLevelExport:
    def test_top_level_attribute_is_a_function_scitex_scholar_ensure_workspace(self):
        # Arrange
        # Act
        attr = scitex_scholar.ensure_workspace
        # Assert
        assert inspect.isfunction(attr)

    def test_top_level_attribute_matches_submodule_function_scitex_scholar_ensure_workspace(self):
        # Arrange
        from scitex_scholar.ensure_workspace import ensure_workspace as submodule_fn
        # Act
        attr = scitex_scholar.ensure_workspace
        # Assert
        assert attr is submodule_fn

    def test_listed_in_dunder_all_scitex_scholar_ensure_workspace(self):
        # Arrange
        # Act
        names = scitex_scholar.__all__
        # Assert
        assert "ensure_workspace" in names

# EOF
