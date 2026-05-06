"""FastMCP server entry point for scitex-scholar.

Exposes a top-level ``mcp`` symbol that ``scitex-dev ecosystem audit-mcp-tools``
discovers as ``scitex_scholar._mcp_server.mcp``. The handlers themselves live
in ``scitex_scholar._mcp.all_handlers``; this module is a thin shim that:

1. Instantiates ``FastMCP``.
2. Registers each ``*_handler`` as an MCP tool named ``scholar_<verb>_<noun>``
   (the ``scholar_`` prefix is the canonical namespace per
   ``~/.claude/skills/scitex/general/03_interface_03_mcp/03_tool-naming.md``).

Run directly:

    python -m scitex_scholar._mcp_server
    # or
    fastmcp run scitex_scholar._mcp_server:mcp
    # or
    scitex-scholar mcp start
"""

from __future__ import annotations

from fastmcp import FastMCP

from ._mcp import all_handlers as _all

mcp = FastMCP(
    name="scitex-scholar",
    instructions=(
        "Scientific literature management — search, DOI resolution, BibTeX "
        "enrichment, PDF download via institutional auth, library "
        "organization, semantic PDF highlighting, and job orchestration. "
        "Every tool is prefixed `scholar_` to namespace it under the unified "
        "scitex MCP server."
    ),
)


def _register_all_handlers() -> None:
    """Wrap every handler in :mod:`._mcp.all_handlers` as a FastMCP tool.

    The handler's signature and docstring are preserved so FastMCP can derive
    the JSON-schema and tool description automatically. Tool names follow the
    ``scholar_<verb>_<noun>`` convention.
    """
    for handler_name in _all.__all__:
        fn = getattr(_all, handler_name)
        tool_name = "scholar_" + handler_name.removesuffix("_handler")
        mcp.tool(name=tool_name)(fn)


_register_all_handlers()


# --------------------------------------------------------------------------- #
# Skills tools (per §5 — every package must expose `<pkg>_skills_list` and    #
# `<pkg>_skills_get` so agents can discover the bundled skill leaves over MCP).#
# --------------------------------------------------------------------------- #


@mcp.tool(name="scholar_skills_list")
def scholar_skills_list() -> dict:
    """List bundled skill leaves shipped with scitex-scholar.

    Returns
    -------
    dict
        ``{"count": int, "skills": [str, …]}`` with leaf basenames
        (without the .md extension).
    """
    from pathlib import Path as _Path

    skills_dir = _Path(__file__).parent / "_skills" / "scitex-scholar"
    if not skills_dir.is_dir():
        return {"count": 0, "skills": []}
    names = sorted(p.stem for p in skills_dir.glob("*.md"))
    return {"count": len(names), "skills": names}


@mcp.tool(name="scholar_skills_get")
def scholar_skills_get(name: str) -> dict:
    """Read a single bundled skill leaf by name (without the .md suffix).

    Parameters
    ----------
    name
        Leaf identifier, e.g. ``04_cli-reference``.

    Returns
    -------
    dict
        ``{"name": str, "path": str, "body": str}`` or
        ``{"name": str, "error": "not found"}`` if the leaf is missing.
    """
    from pathlib import Path as _Path

    skills_dir = _Path(__file__).parent / "_skills" / "scitex-scholar"
    candidate = skills_dir / f"{name}.md"
    if not candidate.is_file():
        return {"name": name, "error": "not found"}
    return {
        "name": name,
        "path": str(candidate),
        "body": candidate.read_text(encoding="utf-8"),
    }


if __name__ == "__main__":
    mcp.run()
