"""Argparse-side handlers for `scitex-scholar mcp {start, list-tools, doctor, install}`.

Mirrors the layout of `scitex-dataset mcp …` so the SciTeX ecosystem CLIs
expose a consistent MCP surface (start / list-tools / doctor / install).
"""

from __future__ import annotations

from typing import Awaitable, Callable

import click
import scitex_logging as logging

# Requested tool names, help and installation snippets are plain stdout results.
# Keep the diagnostic logger independent: a console with this same name would
# reroute errors to stdout and override the configured threshold.
logger = logging.getLogger(__name__)


def _list_tools() -> int:
    from .._mcp.all_handlers import __all__ as _handler_names

    for name in sorted(_handler_names):
        # handlers are registered in the unified server with the
        # `scholar_` prefix and the trailing `_handler` stripped.
        click.echo("scholar_" + name.removesuffix("_handler"))
    return 0


def _doctor() -> int:
    click.echo("Checking MCP dependencies...")
    try:
        import fastmcp  # noqa: F401

        click.echo(f"  OK  fastmcp {fastmcp.__version__}")
    except ImportError:
        click.echo("  NG  fastmcp not installed")
        click.echo("      Install: pip install scitex-scholar[all]")
        return 1

    try:
        from .._mcp import all_handlers as _h

        n = len(_h.__all__)
        click.echo(f"  OK  scitex-scholar handlers ({n} tools)")
    except Exception as exc:  # pragma: no cover — env-dependent
        click.echo(f"  NG  handler import error: {exc}")
        return 1

    click.echo("")
    click.echo("MCP server ready.")
    click.echo("Run: scitex-scholar mcp start")
    return 0


def _install(claude_code: bool) -> int:
    if claude_code:
        click.echo("Add to Claude Code MCP config:")
        click.echo("")
        click.echo('  "scitex-scholar": {')
        click.echo('    "command": "scitex-scholar",')
        click.echo('    "args": ["mcp", "start"]')
        click.echo("  }")
        return 0

    click.echo("scitex-scholar MCP Server Installation")
    click.echo("=" * 40)
    click.echo("")
    click.echo("1. Install: pip install scitex-scholar[all]")
    click.echo("2. Config:  scitex-scholar mcp install --claude-code")
    click.echo("3. Test:    scitex-scholar mcp doctor")
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
        click.echo("usage: scitex-scholar mcp [-h] {start,list-tools,doctor,install} ...")
        click.echo("")
        click.echo("MCP (Model Context Protocol) server commands.")
        click.echo("")
        click.echo("Run `scitex-scholar mcp --help` for full help.")
        return 0

    if sub == "list-tools":
        return _list_tools()
    if sub == "doctor":
        return _doctor()
    if sub == "install":
        return _install(claude_code=getattr(args, "claude_code", False))
    if sub == "start":
        if getattr(args, "dry_run", False):
            click.echo("DRY RUN — would start scitex-scholar MCP server (stdio transport)")
            return 0
        return await run_server()

    logger.error(f"Unknown mcp subcommand: {sub}")
    return 1
