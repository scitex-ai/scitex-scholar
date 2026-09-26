"""FastMCP server entry point for scitex-scholar.

Exposes a top-level ``mcp`` symbol that ``scitex-dev ecosystem audit-mcp-tools``
discovers as ``scitex_scholar._mcp_server.mcp``. The handlers themselves live
in ``scitex_scholar._mcp.all_handlers``; this module is a thin shim that:

1. Instantiates ``FastMCP``.
2. Registers each ``*_handler`` as an MCP tool named ``scholar_<verb>_<noun>``
   (the ``scholar_`` prefix is the canonical namespace per
   ``~/.claude/skills/scitex/general/03_interface_03_mcp/03_tool-naming.md``).

``fastmcp`` lives in the ``[mcp]`` extra, so it is OPTIONAL for the
distribution: a bare ``pip install scitex-scholar`` must not pull the MCP
stack. This module therefore stays IMPORTABLE without it (PS-233 remedy
revised 2026-09-20 -- the previous fix declared fastmcp hard instead of
guarding it) and reports the missing capability two ways: ``MCP_AVAILABLE``
for a programmatic caller, and an ERROR log line naming the extra for a
human. ``mcp`` is ``None`` -- not a stub -- so nothing can mistake this for
a registered server.

Run directly:

    python -m scitex_scholar._mcp_server
    # or
    fastmcp run scitex_scholar._mcp_server:mcp
    # or
    scitex-scholar mcp start
"""

from __future__ import annotations

import scitex_logging as slogging

logger = slogging.getLogger(__name__)

# The ONE install line this module's refusals name.
ALL_EXTRA_HINT = "pip install 'scitex-scholar[all]'"

try:
    from fastmcp import FastMCP
except ImportError:  # fastmcp absent -- the [all]-gated MCP capability only
    FastMCP = None  # type: ignore[assignment]

MCP_AVAILABLE = FastMCP is not None

from ._mcp import all_handlers as _all

if MCP_AVAILABLE:
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
else:
    mcp = None
    logger.error(
        "fastmcp is not installed, so the scitex-scholar MCP server is "
        "unavailable. Install it with: %s",
        ALL_EXTRA_HINT,
    )


def _register_all_handlers() -> None:
    """Wrap every handler in :mod:`._mcp.all_handlers` as a FastMCP tool.

    The handler's signature and docstring are preserved so FastMCP can derive
    the JSON-schema and tool description automatically. Tool names follow the
    ``scholar_<verb>_<noun>`` convention.

    A no-op without fastmcp: there is no server to register against, and the
    module-level ERROR line already said so.
    """
    if mcp is None:
        return
    for handler_name in _all.__all__:
        fn = getattr(_all, handler_name)
        tool_name = "scholar_" + handler_name.removesuffix("_handler")
        mcp.tool(name=tool_name)(fn)


_register_all_handlers()


# --------------------------------------------------------------------------- #
# Skills tools (per §5 — every package must expose `<pkg>_skills_list` and    #
# `<pkg>_skills_get` so agents can discover the bundled skill leaves over MCP).#
# --------------------------------------------------------------------------- #


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


# Registered only when there is a server to register against; the two names
# above stay importable either way (they are pure filesystem helpers).
if MCP_AVAILABLE:
    mcp.tool(name="scholar_skills_list")(scholar_skills_list)
    mcp.tool(name="scholar_skills_get")(scholar_skills_get)


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit(
            "fastmcp is not installed, so the scitex-scholar MCP server "
            f"cannot start. Install it with: {ALL_EXTRA_HINT}"
        )
    mcp.run()
