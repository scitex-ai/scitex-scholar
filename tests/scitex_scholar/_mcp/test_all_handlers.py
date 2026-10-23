"""Smoke import mirror for scitex_scholar._mcp.all_handlers.

Auto-generated subpackage mirror placeholder; replace with real tests
as the module matures. Satisfies the src<->tests mirror audit rule.
"""

import asyncio

import pytest


def test_import_all_handlers_module_loads_via_importorskip():
    """Module loads via ``pytest.importorskip`` and reports its declared name.

    The import itself is the production behaviour under test (a
    missing dependency is reported as a skip, not a pass). The
    single assertion verifies the loaded module's ``__name__``
    matches the requested dotted path — catches accidental aliasing
    and packaging-path drift, which a bare import does not.
    """
    # Arrange
    name = "scitex_scholar._mcp.all_handlers"
    # Act
    mod = pytest.importorskip(name)
    # Assert
    assert mod.__name__ == name


def test_every_registered_handler_is_an_async_callable():
    """The FastMCP server registers every ``__all__`` entry as a tool.

    ``_mcp_server._register_all_handlers`` wraps each name as
    ``scholar_<stem>`` and FastMCP awaits it, so a sync def or a
    non-callable would break the tool surface at serve time instead of
    at commit time (API consistency rule, operator /goal).
    """
    # Arrange
    mod = pytest.importorskip("scitex_scholar._mcp.all_handlers")
    # Act
    bad = [
        name
        for name in mod.__all__
        if not (
            callable(getattr(mod, name, None))
            and asyncio.iscoroutinefunction(getattr(mod, name))
        )
    ]
    # Assert
    assert bad == []


def test_highlight_pdf_is_registered_alongside_its_handler():
    """Highlight PDF is one registered tool, not two drifting surfaces.

    Operator 2026-10-22 (card scholar-mcp-highlight-pdf-schema-gap):
    highlight_pdf_handler is re-exported by all_handlers (the live
    FastMCP registration incl. ``scholar_highlight_pdf`` in
    ``mcp list-tools``), and pdf_tool_schemas carries NO competing
    manual duplicate -- that module lists download/validate/parse only
    (legacy mcp_server.py is deprecated). One assertion: the live
    surface has exactly one highlight source of truth.
    """
    # Arrange
    handlers = pytest.importorskip("scitex_scholar._mcp.all_handlers")
    schemas = pytest.importorskip("scitex_scholar._mcp.pdf_tool_schemas")
    # Act
    single = (
        hasattr(handlers, "highlight_pdf_handler"),
        "scholar_highlight_pdf"
        in [
            "scholar_" + n.removesuffix("_handler")
            for n in handlers.__all__
        ],
        not any(
            "highlight" in t.name for t in schemas.get_pdf_tool_schemas()
        ),
    )
    # Assert
    assert single == (True, True, True)
