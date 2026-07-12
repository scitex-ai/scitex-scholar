#!/usr/bin/env python3
"""Tests for the `gui` CLI group.

Mirrors `src/scitex_scholar/_cli/gui.py`. `scitex_dev.gui_runtime.GuiRuntime`
is an optional dependency (not yet on PyPI as of writing -- merged to
scitex-dev's develop branch, 2026-07-12); these tests must pass whether or
not it happens to be importable in the CI environment, so `status`/`stop`
assert on the *contract* (never crash; either report real state or the
documented upgrade-guidance message) rather than on one specific outcome.
"""

from __future__ import annotations

from click.testing import CliRunner

from scitex_scholar._cli_main import cli

_GUI_RUNTIME_MISSING_MSG = "scitex-dev is missing gui_runtime"


def test_gui_help_lists_all_four_verbs():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert all(v in result.output for v in ("open", "serve", "status", "stop"))


def test_gui_group_has_no_positional_argument():
    """Per the ecosystem gui-commands skill: `gui` is a group only -- a bare
    invocation must print the usage/commands listing, not fail trying to
    consume a stray positional argument (which would misparse `gui serve`
    as a SOURCE value instead of resolving the `serve` subcommand)."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui"])
    # Assert
    assert "Usage:" in result.output


def test_gui_status_never_crashes_with_an_unhandled_traceback():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "status"])
    # Assert
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_gui_status_reports_real_state_or_the_documented_upgrade_message():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "status"])
    # Assert
    assert (
        _GUI_RUNTIME_MISSING_MSG in result.output
        or "running" in result.output
        or "not running" in result.output
    )


def test_gui_stop_never_crashes_with_an_unhandled_traceback():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "stop"])
    # Assert
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_gui_serve_help_shows_port_and_host_options():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--port" in result.output and "--host" in result.output


def test_gui_serve_help_does_not_offer_a_no_browser_flag():
    """`serve` is headless-only by ecosystem convention -- browser-launching
    is exclusively `open`'s job, so `--no-browser` must never appear here."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--no-browser" not in result.output


def test_gui_open_help_shows_port_and_host_options():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "open", "--help"])
    # Assert
    assert "--port" in result.output and "--host" in result.output


def test_gui_serve_default_port_is_31297():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "31297" in result.output
