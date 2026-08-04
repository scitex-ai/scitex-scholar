#!/usr/bin/env python3
"""Tests for the `gui` CLI group.

Mirrors `src/scitex_scholar/_cli/gui.py`. GUI lifecycle (state file,
liveness, port-holder identification, orphan reclaim) is delegated to
`scitex_app.embed`; scitex-app is an optional dependency (the `server`
extra), so the tests that only assert the CLI *contract* must pass
whether or not it is importable -- they accept either the real state or
the documented install-guidance message.

The port-holder tests are different: they exercise scholar's own
three-valued branching in `gui open`, so they drive a REAL process
holding a REAL port and read what the CLI actually prints. No
monkeypatch, no mocks (STX-NM002) -- a test that only passes because
production internals were rewritten is not testing production.
"""

from __future__ import annotations

import ast
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_scholar import _cli
from scitex_scholar._cli_main import cli

_SCITEX_APP_MISSING_MSG = "scitex-app is not installed"

# Read via the `_cli` PACKAGE dir, not by importing `_cli.gui`: every
# `_cli/*` module imports its Click scaffolding from `_cli_main`, which
# imports them all back at the bottom, so `import scitex_scholar._cli.gui`
# on a cold interpreter raises a circular-import ImportError. `_cli/
# __init__.py` imports nothing, so this path is order-independent.
_GUI_SOURCE = (Path(_cli.__file__).parent / "gui.py").read_text()

# Holds a port open without looking like scholar: argv is the bare
# interpreter plus this inline script, so `argv_is_ours` must answer False.
_HOLDER_SCRIPT = (
    "import socket,sys,time\n"
    "s=socket.socket()\n"
    "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
    "s.bind(('127.0.0.1',int(sys.argv[1])))\n"
    "s.listen(5)\n"
    "time.sleep(60)\n"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _hold_port(*extra_argv: str):
    """Start a real process LISTENing on a free port; return (port, proc).

    `extra_argv` lands in the holder's argv, which is the only thing
    ownership is proven from -- so passing the package token produces a
    holder scitex-app identifies as OURS, and passing nothing produces a
    stranger. Nothing is faked: both are live processes on live ports.
    """
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLDER_SCRIPT, str(port), *extra_argv],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd="/",
    )
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return port, proc
        time.sleep(0.1)
    proc.kill()
    pytest.fail(f"holder process never bound port {port}")


@pytest.fixture
def foreign_port_holder():
    """Yield a port genuinely held by a process that is NOT a Scholar GUI."""
    port, proc = _hold_port()
    yield port
    proc.kill()
    proc.wait(timeout=10)


@pytest.fixture
def orphaned_scholar_port_holder():
    """Yield a port held by a process scitex-app identifies as OUR OWN.

    This is the case `gui status` structurally cannot see (no live entry
    in the state file) and that the old socket probe reported as a
    stranger.
    """
    port, proc = _hold_port("scitex_scholar")
    yield port
    proc.kill()
    proc.wait(timeout=10)


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


def test_gui_status_reports_real_state_or_the_documented_install_message():
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "status"])
    # Assert
    assert (
        _SCITEX_APP_MISSING_MSG in result.output
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


def test_gui_serve_help_offers_the_force_flag():
    """`--force` is the point of the shared launcher: it reclaims OUR OWN
    orphan, the case `gui status` structurally cannot see."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--force" in result.output


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


def test_default_port_is_imported_not_restated():
    """The port must have ONE definition. `_cli/gui.py` and `_server.py`
    previously "just agreed" on the literal 31297 -- a coincidence kept by
    hand. Re-adding a local `DEFAULT_PORT = ...` here fails this test."""
    # Arrange
    tree = ast.parse(_GUI_SOURCE)
    # Act
    assigned = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    # Assert
    assert "DEFAULT_PORT" not in assigned


def test_gui_module_does_not_reimplement_port_probing():
    """Port identification belongs to `scitex_app.embed.gui_port_holder`,
    which answers WHO holds the port (three-valued). A local `socket` probe
    can only answer "something is there", which is how the previous version
    reported our own orphan as a stranger. Importing socket here again is
    that regression."""
    # Arrange
    tree = ast.parse(_GUI_SOURCE)
    # Act
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    # Assert
    assert "socket" not in imported


def test_gui_lifecycle_is_not_delegated_to_two_packages_at_once():
    """`scitex_dev.gui_runtime` was the previous lifecycle owner. Keeping it
    alongside `scitex_app.embed` would be two owners of one state file."""
    # Arrange
    source = _GUI_SOURCE
    # Act
    still_present = "scitex_dev.gui_runtime" in source
    # Assert
    assert not still_present


@pytest.mark.skipif(
    not Path("/proc").is_dir(),
    reason="port-holder identification reads /proc (Linux-only)",
)
def test_gui_open_names_a_foreign_port_holder_as_a_different_process(
    foreign_port_holder,
):
    """The honesty fix: a holder that is provably NOT ours is reported as a
    different process -- not as "an orphaned Scholar GUI", and not as the old
    catch-all "not a Scholar GUI we started" that covered both cases."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "open", "--port", str(foreign_port_holder)])
    # Assert
    assert (
        "different process" in result.output
        or _SCITEX_APP_MISSING_MSG in result.output
    )


@pytest.mark.skipif(
    not Path("/proc").is_dir(),
    reason="port-holder identification reads /proc (Linux-only)",
)
def test_gui_open_refuses_to_start_when_the_port_is_held(foreign_port_holder):
    """Refusal must be an exit code, not only a printed sentence: `gui open`
    gets scripted against, and a 0 here would read as "the GUI is up"."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "open", "--port", str(foreign_port_holder)])
    # Assert
    assert result.exit_code == 1


@pytest.mark.skipif(
    not Path("/proc").is_dir(),
    reason="port-holder identification reads /proc (Linux-only)",
)
def test_gui_open_does_not_blame_a_foreign_holder_on_an_orphan(
    foreign_port_holder,
):
    """The orphan message prescribes `gui serve --force`, which then tries to
    kill the holder. Printing it for someone else's process is exactly what
    the three-valued PortHolder exists to prevent."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "open", "--port", str(foreign_port_holder)])
    # Assert
    assert "ORPHANED" not in result.output


@pytest.mark.skipif(
    not Path("/proc").is_dir(),
    reason="port-holder identification reads /proc (Linux-only)",
)
def test_gui_open_identifies_our_own_orphan_rather_than_calling_it_a_stranger(
    orphaned_scholar_port_holder,
):
    """The case the whole adoption is for. The previous socket probe could
    only see "something is listening" and reported our own orphan with the
    stranger message -- leaving the user no way to reclaim their own port."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["gui", "open", "--port", str(orphaned_scholar_port_holder)]
    )
    # Assert
    assert "ORPHANED" in result.output


@pytest.mark.skipif(
    not Path("/proc").is_dir(),
    reason="port-holder identification reads /proc (Linux-only)",
)
def test_gui_open_prescribes_force_for_our_own_orphan(
    orphaned_scholar_port_holder,
):
    """An error that only says what broke is half-written: the orphan branch
    must name the command that fixes it."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli, ["gui", "open", "--port", str(orphaned_scholar_port_holder)]
    )
    # Assert
    assert "gui serve --force" in result.output


# EOF
