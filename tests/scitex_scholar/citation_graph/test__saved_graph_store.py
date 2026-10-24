"""Saved-graph store CUI: schema declares, file stays authoritative.

One assertion per test (STX-TQ007): tuple compares.
"""

from scitex_scholar.citation_graph import _saved_graph_store as m


def test_store_declares_schema_with_user_root_and_graph_id_identity():
    # Arrange
    schema = m.schema()
    # Act
    identity = sorted(schema.identity_fields)
    # Assert
    assert (schema.name, identity) == (m.TABLE, ["graph_id", "user_root"])


def test_hook_rules_declare_five_scholar_scope_rules():
    # Arrange
    from scitex_scholar._hook_rules import provide
    # Act
    ids = sorted(r.id for r in provide())
    # Assert
    assert ids == [
        "scholar.bulk-verbs-explicit-rows-only",
        "scholar.file-authoritative-store-derived",
        "scholar.per-user-root-scope",
        "scholar.search-fails-closed",
        "scholar.thin-view-cui-owns-logic",
    ]


def test_hooks_entry_point_registered_in_pyproject():
    # Arrange
    from pathlib import Path
    # Act
    pyproject = (Path(__file__).parents[3] / "pyproject.toml").read_text()
    # Assert
    assert (
        '[project.entry-points."scitex_dev.hooks"]' in pyproject,
        "scitex_scholar._hook_rules:provide" in pyproject,
    ) == (True, True)
