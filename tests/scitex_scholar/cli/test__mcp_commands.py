"""Real stream contracts for the legacy argparse MCP handlers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import scitex_scholar


def _probe(tmp_path: Path, body: str, level: str = "error"):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PYTHONPATH": str(Path(scitex_scholar.__file__).resolve().parent.parent),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    script = (
        "import asyncio, types\n"
        "import scitex_logging as logging\n"
        f"logging.configure(level={level!r}, enable_file=False, "
        "capture_prints=False)\n"
        "from scitex_scholar.cli import _mcp_commands as commands\n"
        + body
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_unknown_command_is_an_error_on_stderr(tmp_path):
    result = _probe(
        tmp_path,
        "result = asyncio.run(commands.run_mcp_subcommand("
        "types.SimpleNamespace(mcp_command='unknown'), run_server=None))\n"
        "assert result == 1\n",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "Unknown mcp subcommand: unknown" in result.stderr


def test_unknown_command_respects_critical_level_set_after_import(tmp_path):
    result = _probe(
        tmp_path,
        "logging.set_level('critical')\n"
        "result = asyncio.run(commands.run_mcp_subcommand("
        "types.SimpleNamespace(mcp_command='unknown'), run_server=None))\n"
        "assert result == 1\n",
        level="info",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_tool_names_are_plain_complete_results_at_any_log_level(tmp_path, level):
    from scitex_scholar._mcp.all_handlers import __all__ as handler_names

    result = _probe(tmp_path, "assert commands._list_tools() == 0\n", level)
    expected = [
        "scholar_" + name.removesuffix("_handler")
        for name in sorted(handler_names)
    ]
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.splitlines() == expected


@pytest.mark.parametrize("level", ["info", "critical"])
def test_config_snippet_remains_valid_plain_json_content(tmp_path, level):
    result = _probe(
        tmp_path, "assert commands._install(claude_code=True) == 0\n", level
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    heading, snippet = result.stdout.split("\n\n", 1)
    assert heading == "Add to Claude Code MCP config:"
    assert json.loads("{" + snippet + "}") == {
        "scitex-scholar": {"command": "scitex-scholar", "args": ["mcp", "start"]}
    }


def test_dry_run_dispatch_preserves_plain_launch_plan(tmp_path):
    result = _probe(
        tmp_path,
        "result = asyncio.run(commands.run_mcp_subcommand("
        "types.SimpleNamespace(mcp_command='start', dry_run=True), "
        "run_server=None))\nassert result == 0\n",
        level="critical",
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == (
        "DRY RUN — would start scitex-scholar MCP server (stdio transport)\n"
    )
