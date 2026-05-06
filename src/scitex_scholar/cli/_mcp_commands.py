"""Argparse-side handlers for `scitex-scholar mcp {start, list-tools, doctor, install}`.

Mirrors the layout of `scitex-dataset mcp …` so the SciTeX ecosystem CLIs
expose a consistent MCP surface (start / list-tools / doctor / install).
"""

from __future__ import annotations

from typing import Awaitable, Callable

import scitex_logging as logging

logger = logging.getLogger(__name__)


def _list_tools() -> int:
    from .._mcp.all_handlers import __all__ as _handler_names

    for name in sorted(_handler_names):
        # handlers are registered in the unified server with the
        # `scholar_` prefix and the trailing `_handler` stripped.
        print("scholar_" + name.removesuffix("_handler"))
    return 0


def _doctor() -> int:
    print("Checking MCP dependencies...")
    try:
        import fastmcp  # noqa: F401

        print(f"  OK  fastmcp {fastmcp.__version__}")
    except ImportError:
        print("  NG  fastmcp not installed")
        print("      Install: pip install scitex-scholar[mcp]")
        return 1

    try:
        from .._mcp import all_handlers as _h

        n = len(_h.__all__)
        print(f"  OK  scitex-scholar handlers ({n} tools)")
    except Exception as exc:  # pragma: no cover — env-dependent
        print(f"  NG  handler import error: {exc}")
        return 1

    print()
    print("MCP server ready.")
    print("Run: scitex-scholar mcp start")
    return 0


def _install(claude_code: bool) -> int:
    if claude_code:
        print("Add to Claude Code MCP config:")
        print()
        print('  "scitex-scholar": {')
        print('    "command": "scitex-scholar",')
        print('    "args": ["mcp", "start"]')
        print("  }")
        return 0

    print("scitex-scholar MCP Server Installation")
    print("=" * 40)
    print()
    print("1. Install: pip install scitex-scholar[mcp]")
    print("2. Config:  scitex-scholar mcp install --claude-code")
    print("3. Test:    scitex-scholar mcp doctor")
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
        print("usage: scitex-scholar mcp [-h] {start,list-tools,doctor,install} ...")
        print()
        print("MCP (Model Context Protocol) server commands.")
        print()
        print("Run `scitex-scholar mcp --help` for full help.")
        return 0

    if sub == "list-tools":
        return _list_tools()
    if sub == "doctor":
        return _doctor()
    if sub == "install":
        return _install(claude_code=getattr(args, "claude_code", False))
    if sub == "start":
        if getattr(args, "dry_run", False):
            print("DRY RUN — would start scitex-scholar MCP server (stdio transport)")
            return 0
        return await run_server()

    logger.error(f"Unknown mcp subcommand: {sub}")
    return 1
