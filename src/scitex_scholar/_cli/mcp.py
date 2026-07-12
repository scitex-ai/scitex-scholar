#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/mcp.py

"""``mcp`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.mcp import mcp`` +
``cli.add_command(mcp)``.
"""

from __future__ import annotations

import asyncio
import json as _json
import sys
from typing import Any

import click

from .._cli_main import CONTEXT_SETTINGS

# ---------------------------------------------------------------------------
# Group: mcp
# ---------------------------------------------------------------------------


@click.group(context_settings=CONTEXT_SETTINGS)
def mcp() -> None:
    """MCP (Model Context Protocol) server commands."""


@mcp.command("start")
@click.option("--dry-run", is_flag=True, help="Print launch plan without starting.")
@click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive.")
def mcp_start(dry_run, yes):
    """Start the scitex-scholar MCP server.

    \b
    Example:
      $ scitex-scholar mcp start
      $ scitex-scholar mcp start --dry-run
    """
    if dry_run:
        click.echo("DRY RUN — would start scitex-scholar MCP server (stdio transport)")
        return
    sys.exit(asyncio.run(_run_mcp_server_async()))


async def _run_mcp_server_async() -> int:
    import inspect

    from ..mcp_server import main as mcp_main

    result: Any = mcp_main()
    if inspect.isawaitable(result):
        await result
    return 0


@mcp.command("list-tools")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def mcp_list_tools(as_json):
    """List available MCP tools.

    \b
    Example:
      $ scitex-scholar mcp list-tools
      $ scitex-scholar mcp list-tools --json
    """
    from .._mcp.all_handlers import __all__ as _handler_names

    tools = [
        "scholar_" + name.removesuffix("_handler") for name in sorted(_handler_names)
    ]
    if as_json:
        click.echo(_json.dumps({"tools": tools, "count": len(tools)}, indent=2))
        return
    for t in tools:
        click.echo(t)


@mcp.command("doctor")
def mcp_doctor():
    """Check MCP server dependencies.

    \b
    Example:
      $ scitex-scholar mcp doctor
    """
    click.echo("Checking MCP dependencies...")
    try:
        import fastmcp  # type: ignore

        click.secho(f"  OK  fastmcp {fastmcp.__version__}", fg="green")
    except ImportError:
        click.secho("  NG  fastmcp not installed", fg="red")
        click.echo("      Install: pip install scitex-scholar[mcp]")
        sys.exit(1)
    try:
        from .._mcp import all_handlers as _h

        click.secho(
            f"  OK  scitex-scholar handlers ({len(_h.__all__)} tools)", fg="green"
        )
    except Exception as exc:  # pragma: no cover
        click.secho(f"  NG  handler import error: {exc}", fg="red")
        sys.exit(1)
    click.echo("\nMCP server ready.")
    click.echo("Run: scitex-scholar mcp start")


@mcp.command("install")
@click.option("--claude-code", is_flag=True, help="Show Claude Code config snippet.")
@click.option("--dry-run", is_flag=True, help="Print plan without executing.")
@click.option("--yes", "-y", is_flag=True)
def mcp_install(claude_code, dry_run, yes):
    """Show MCP installation instructions.

    \b
    Example:
      $ scitex-scholar mcp install
      $ scitex-scholar mcp install --claude-code
    """
    if dry_run:
        click.echo(
            f"DRY RUN — would print install instructions (claude_code={claude_code})"
        )
        return
    if claude_code:
        click.echo("Add to Claude Code MCP config:")
        click.echo()
        click.echo('  "scitex-scholar": {')
        click.echo('    "command": "scitex-scholar",')
        click.echo('    "args": ["mcp", "start"]')
        click.echo("  }")
        return
    click.echo("scitex-scholar MCP Server Installation")
    click.echo("=" * 40)
    click.echo()
    click.echo("1. Install: pip install scitex-scholar[mcp]")
    click.echo("2. Config:  scitex-scholar mcp install --claude-code")
    click.echo("3. Test:    scitex-scholar mcp doctor")


# EOF
