"""Regression test: the import paths scitex-hub deep-imports must keep resolving.

scitex-hub's scholar_app consumes scitex-scholar via
apps/workspace/scholar_app/integrations/scitex_scholar.py:

    from scitex.scholar import ScholarConfig
    from scitex.scholar.pipelines.SearchQueryParser import SearchQueryParser
    from scitex.scholar.search_engines.ScholarSearchEngine import ScholarSearchEngine

(`scitex.scholar` is the umbrella alias for this package.) If a future
refactor relocates these symbols, hub's search silently degrades to
SCITEX_AVAILABLE=False with no loud error. This test makes such a move
fail loudly in THIS package's CI first. Coordinated with scitex-hub
(#scholar-public-import-contract); do not relocate these without a heads-up.

A clean top-level facade (`from scitex_scholar import ScholarSearchEngine,
SearchQueryParser`) is also asserted so consumers can migrate off the
deep-internal paths.
"""

import scitex_scholar


class TestHubDeepImportContract:
    def test_deep_import_scholar_search_engine_resolves(self):
        # Arrange
        # Act
        from scitex_scholar.search_engines.ScholarSearchEngine import (
            ScholarSearchEngine,
        )
        # Assert
        assert isinstance(ScholarSearchEngine, type)

    def test_deep_import_search_query_parser_resolves(self):
        # Arrange
        # Act
        from scitex_scholar.pipelines.SearchQueryParser import SearchQueryParser
        # Assert
        assert isinstance(SearchQueryParser, type)

    def test_deep_import_scholar_config_resolves(self):
        # Arrange
        # Act
        from scitex_scholar.config import ScholarConfig
        # Assert
        assert isinstance(ScholarConfig, type)


class TestTopLevelSearchFacade:
    def test_scholar_search_engine_top_level_matches_submodule(self):
        # Arrange -- read the lazy top-level attribute BEFORE importing the
        # submodule directly, so the PEP 562 re-export is exercised (mirrors
        # test_ensure_workspace_export's import-order note).
        top_level = scitex_scholar.ScholarSearchEngine
        # Act
        from scitex_scholar.search_engines.ScholarSearchEngine import (
            ScholarSearchEngine as submodule_cls,
        )
        # Assert
        assert top_level is submodule_cls

    def test_search_query_parser_top_level_matches_submodule(self):
        # Arrange
        top_level = scitex_scholar.SearchQueryParser
        # Act
        from scitex_scholar.pipelines.SearchQueryParser import (
            SearchQueryParser as submodule_cls,
        )
        # Assert
        assert top_level is submodule_cls

    def test_search_facade_listed_in_dunder_all(self):
        # Arrange
        names = scitex_scholar.__all__
        # Act
        both_present = {"ScholarSearchEngine", "SearchQueryParser"} <= set(names)
        # Assert
        assert both_present

# EOF
