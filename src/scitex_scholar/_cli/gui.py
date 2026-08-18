#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/gui.py

"""``gui`` command group for the Scholar CLI.

Follows the ecosystem-wide canonical shape (scitex-dev skill
``_skills/general/03_interface/02_cli/19_gui-commands.md``): every
browser-based surface a package ships mounts under one group, ``gui``,
with exactly four verbs -- ``open``, ``serve``, ``status``, ``stop``.
Lifecycle bookkeeping (pid/port/host state file, liveness, idempotent
stop, port-holder identification) is delegated to ``scitex_app.embed``
rather than reimplemented here (scitex-writer and figrecipe
independently wrote the same ~140 lines before it was generalized).

``serve`` is the foreground, headless server (no ``--no-browser`` flag
-- browser-launching is exclusively ``open``'s job). ``open`` auto-serves
in a detached background process if nothing is already running, then
opens the browser. Default port 31297 (the fixed scitex-scholar slot
in the ecosystem's 3129X standalone-GUI port block), imported from
``_django._server`` so the launcher and the CLI cannot drift apart.

Scholar owns WHERE its runtime state lives (``_state_path()``, derived
from ``ScholarConfig``, so ``gui.json`` sits with the rest of scholar's
state under ``.scitex/scholar/``); scitex-app owns HOW that state is
read, written and healed. ``state_path=`` is the dependency-injection
seam scitex-app provides for exactly this -- taking its default would
scatter scholar's state across two directories.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Optional

import click

from ._scaffolding import CONTEXT_SETTINGS
from .._django._server import DEFAULT_PORT

DEFAULT_HOST = "127.0.0.1"

# Passed to scitex-app as `package`. This is the DISTRIBUTION name on
# purpose: it is what scitex-app prints back in its remedy lines, and it
# is the string `argv_is_ours()` matches against a running process's argv
# (`python -m scitex_scholar ...` normalizes to the same token). A short
# "scholar" would print a command that does not exist.
PACKAGE = "scitex-scholar"


def _state_path():
    """Path of the GUI runtime-state file (scholar decides; scitex-app uses)."""
    from ..config import ScholarConfig

    return ScholarConfig().path_manager.scholar_dir / "runtime" / "gui.json"


def _embed():
    """Return `scitex_app.embed`, or exit with an actionable message.

    ONLY the import is guarded: an ImportError raised from inside
    scitex-app is a real bug, not an absent optional dependency, and
    must not be reported as "install scitex-app".
    """
    try:
        import scitex_app.embed as embed
    except ImportError:
        click.secho(
            "scitex-app is not installed -- the GUI lifecycle (serve/status/"
            "stop) is delegated to it. Install it with: "
            "pip install 'scitex-scholar[server]' (needs scitex-app >= 0.5.0).",
            fg="red",
            err=True,
        )
        sys.exit(1)

    return embed


@click.group(context_settings=CONTEXT_SETTINGS)
def gui() -> None:
    """Scholar's browser-based GUI (paper library / citation graph)."""


@gui.command("open")
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--db-path", default=None, help="Path to CrossRef SQLite database.")
def gui_open(port: int, host: str, db_path: Optional[str]) -> None:
    """Open the Scholar GUI in a browser, auto-serving if not already running.

    \b
    Example:
      $ scitex-scholar gui open
    """
    import webbrowser

    embed = _embed()
    state_path = _state_path()
    current = embed.gui_status(PACKAGE, state_path=state_path)
    if current.get("running"):
        click.echo(f"Already running at {current['url']} -- opening browser.")
        webbrowser.open(current["url"])
        return

    # Nothing is recorded in our state file. That does NOT prove the port is
    # free, and it does not prove a holder is a stranger: the previous
    # version said "not a Scholar GUI we started" for every holder, which is
    # a confident wrong answer when the holder is our OWN orphan. Ask who is
    # actually there, and let each of the three answers say its own thing.
    holder = embed.gui_port_holder(port, PACKAGE)
    if holder.in_use:
        if holder.ours:
            click.secho(
                f"{host}:{port} is held by an ORPHANED Scholar GUI (pid "
                f"{holder.pid}) -- it died without clearing its state file, "
                f"so `gui status` cannot see it. Reclaim it with:\n"
                f"  scitex-scholar gui serve --force",
                fg="red",
                err=True,
            )
        elif holder.ours is False:
            click.secho(
                f"Refusing to start: {host}:{port} is held by a different "
                f"process (pid {holder.pid}, {holder.name}). Free it, or pass "
                f"--port to use another one. Not opening the browser.",
                fg="red",
                err=True,
            )
        else:
            click.secho(
                f"Refusing to start: {host}:{port} is in use, but /proc could "
                f"not be read, so whether it is ours is UNKNOWN -- not "
                f"guessing, and not opening the browser. Pass --port to use "
                f"another one.",
                fg="red",
                err=True,
            )
        sys.exit(1)

    click.echo(f"Starting Scholar GUI server on {host}:{port}...")
    log_path = state_path.with_name("gui-serve.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "scitex_scholar", "gui", "serve", "--port", str(port), "--host", host]
    if db_path:
        cmd += ["--db-path", db_path]
    with open(log_path, "wb") as log_file:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    url = f"http://{host}:{port}"
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if embed.gui_status(PACKAGE, state_path=state_path).get("running"):
            webbrowser.open(url)
            click.echo(f"Scholar GUI running at {url}")
            return
        time.sleep(0.2)

    click.secho(
        f"Server did not come up within 10s -- not opening the browser. "
        f"Last output from {log_path}:",
        fg="red",
        err=True,
    )
    try:
        tail = log_path.read_text()[-2000:]
        click.echo(tail, err=True)
    except OSError:
        pass
    sys.exit(1)


@gui.command("serve")
@click.option("--port", default=DEFAULT_PORT, show_default=True, type=int)
@click.option("--host", default=DEFAULT_HOST, show_default=True)
@click.option("--db-path", default=None, help="Path to CrossRef SQLite database.")
@click.option(
    "--force",
    is_flag=True,
    help="Stop a previous Scholar GUI -- recorded OR orphaned -- then serve here.",
)
def gui_serve(port: int, host: str, db_path: Optional[str], force: bool) -> None:
    """Run the Scholar GUI server in the foreground (headless; Ctrl-C to stop).

    \b
    Example:
      $ scitex-scholar gui serve --port 31297
      $ scitex-scholar gui serve --force
    """
    from functools import partial

    from .._django import _server

    # `serve_gui` owns the whole guarded launch: refuse a live second
    # instance, self-heal a stale recorded pid, identify a foreign port
    # holder from its argv, reclaim our own orphan under --force, record
    # state, run, and clear state in a `finally`. The local pre-flight
    # socket probe and write_state/clear_state pair this replaces were a
    # second implementation of that logic, and a weaker one: it could not
    # tell our orphan from a stranger, so it refused both with the same
    # message. There is no broad `except Exception` here any more either --
    # the state file is cleared by serve_gui's `finally` regardless, so
    # swallowing the traceback only cost us the diagnosis.
    exit_code = _embed().serve_gui(
        package=PACKAGE,
        project_dir=os.getcwd(),
        port=port,
        host=host,
        force=force,
        run_server=partial(
            _server.run, port=port, host=host, db_path=db_path, open_browser=False
        ),
        state_path=_state_path(),
    )
    sys.exit(exit_code)


@gui.command("status")
@click.option("--json", "as_json", is_flag=True)
def gui_status(as_json: bool) -> None:
    """Report whether the Scholar GUI server is running.

    \b
    Example:
      $ scitex-scholar gui status
    """
    import json as _json

    state = _embed().gui_status(PACKAGE, state_path=_state_path())
    if as_json:
        click.echo(_json.dumps(state, indent=2))
        return
    if state.get("running"):
        click.echo(f"running at {state['url']} (pid {state.get('pid')})")
    else:
        click.echo("not running")


@gui.command("stop")
@click.option("--dry-run", is_flag=True, help="Print what would happen without stopping.")
@click.option("--yes", "-y", is_flag=True, help="Confirm stopping the server.")
def gui_stop(dry_run: bool, yes: bool) -> None:
    """Stop the running Scholar GUI server.

    \b
    Example:
      $ scitex-scholar gui stop -y
      $ scitex-scholar gui stop --dry-run
    """
    embed = _embed()
    state_path = _state_path()
    current = embed.gui_status(PACKAGE, state_path=state_path)
    if not current.get("running"):
        click.echo("Not running.")
        return
    if dry_run:
        click.echo(f"DRY RUN -- would stop pid {current.get('pid')} ({current.get('url')})")
        return
    if not yes:
        click.secho(
            "Refusing to stop without --yes/-y (or use --dry-run to preview).",
            fg="yellow",
            err=True,
        )
        sys.exit(1)
    result = embed.gui_stop(PACKAGE, state_path=state_path)
    if result.get("stopped"):
        click.echo(f"Stopped (pid {result.get('pid')}).")
    else:
        click.secho(f"Failed to stop: {result.get('error')}", fg="red", err=True)
        sys.exit(1)


# EOF
