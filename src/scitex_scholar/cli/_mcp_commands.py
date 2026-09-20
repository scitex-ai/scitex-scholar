"""Argparse-side handlers for `scitex-scholar mcp {start, list-tools, doctor, install}`.

Mirrors the layout of `scitex-dataset mcp …` so the SciTeX ecosystem CLIs
expose a consistent MCP surface (start / list-tools / doctor / install).
"""

from __future__ import annotations

from typing import Awaitable, Callable

import scitex_logging as logging

console = logging.getConsole(__name__)

logger = logging.getLogger(__name__)


def _list_tools() -> int:
    from .._mcp.all_handlers import __all__ as _handler_names

    for name in sorted(_handler_names):
        # handlers are registered in the unified server with the
        # `scholar_` prefix and the trailing `_handler` stripped.
        console.info("scholar_" + name.removesuffix("_handler"))
    return 0


def _doctor() -> int:
    console.info("Checking MCP dependencies...")
    try:
        import fastmcp  # noqa: F401

        console.info(f"  OK  fastmcp {fastmcp.__version__}")
    except ImportError:
        console.info("  NG  fastmcp not installed")
        console.info("      Install: pip install scitex-scholar[mcp]")
        return 1

    try:
        from .._mcp import all_handlers as _h

        n = len(_h.__all__)
        console.info(f"  OK  scitex-scholar handlers ({n} tools)")
    except Exception as exc:  # pragma: no cover — env-dependent
        console.info(f"  NG  handler import error: {exc}")
        return 1

    console.info("")
    console.info("MCP server ready.")
    console.info("Run: scitex-scholar mcp start")
    return 0


def _install(claude_code: bool) -> int:
    if claude_code:
        console.info("Add to Claude Code MCP config:")
        console.info("")
        console.info('  "scitex-scholar": {')
        console.info('    "command": "scitex-scholar",')
        console.info('    "args": ["mcp", "start"]')
        console.info("  }")
        return 0

    console.info("scitex-scholar MCP Server Installation")
    console.info("=" * 40)
    console.info("")
    console.info("1. Install: pip install scitex-scholar[mcp]")
    console.info("2. Config:  scitex-scholar mcp install --claude-code")
    console.info("3. Test:    scitex-scholar mcp doctor")
    return 0


async def run_mcp_subcommand(args, *, run_server: Callable[[], Awaitable[int]]) -> int:
    """Dispatch on `args.mcp_command`.

    `run_server` is the package's existing async server entry point — passed
    in so this module doesn't need to import the legacy `mcp_server` module
    at parse time.
    """
    sub = getattr(args, "mcp_command", None)

    if sub is None:
        # Bare `scitex-scholar mcp` — print help, exit 0 (matches scitex-dataset).
        # The user is expected to call `mcp start` explicitly.
        console.info("usage: scitex-scholar mcp [-h] {start,list-tools,doctor,install} ...")
        console.info("")
        console.info("MCP (Model Context Protocol) server commands.")
        console.info("")
        console.info("Run `scitex-scholar mcp --help` for full help.")
        return 0

    if sub == "list-tools":
        return _list_tools()
    if sub == "doctor":
        return _doctor()
    if sub == "install":
        return _install(claude_code=getattr(args, "claude_code", False))
    if sub == "start":
        if getattr(args, "dry_run", False):
            console.info("DRY RUN — would start scitex-scholar MCP server (stdio transport)")
            return 0
        return await run_server()

    logger.error(f"Unknown mcp subcommand: {sub}")
    return 1
