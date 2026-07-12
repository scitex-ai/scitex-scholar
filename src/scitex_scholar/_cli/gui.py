#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/gui.py

"""``gui`` command group for the Scholar CLI.

Follows the ecosystem-wide canonical shape (scitex-dev skill
``_skills/general/03_interface/02_cli/19_gui-commands.md``): every
browser-based surface a package ships mounts under one group, ``gui``,
with exactly four verbs -- ``open``, ``serve``, ``status``, ``stop``.
Lifecycle bookkeeping (pid/port/host state file, liveness, idempotent
stop) is delegated to ``scitex_dev.gui_runtime.GuiRuntime`` rather than
reimplemented here (scitex-writer and figrecipe independently wrote
the same ~140 lines before it was generalized).

``serve`` is the foreground, headless server (no ``--no-browser`` flag
-- browser-launching is exclusively ``open``'s job). ``open`` auto-serves
in a detached background process if nothing is already running, then
opens the browser. Default port 31297 (the fixed scitex-scholar slot
in the ecosystem's 3129X standalone-GUI port block).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from typing import Optional

import click

from .._cli_main import CONTEXT_SETTINGS

DEFAULT_PORT = 31297
DEFAULT_HOST = "127.0.0.1"


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already accepting connections on (host, port)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _runtime():
    try:
        from scitex_dev.gui_runtime import GuiRuntime
    except ImportError:
        click.secho(
            "scitex-dev is missing gui_runtime -- run `pip install -U "
            "scitex-dev` (needs a release containing scitex_dev.gui_runtime).",
            fg="red",
            err=True,
        )
        sys.exit(1)

    from ..config import ScholarConfig

    state_path = ScholarConfig().path_manager.scholar_dir / "runtime" / "gui.json"
    return GuiRuntime(state_path)


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

    runtime = _runtime()
    current = runtime.status()
    if current.get("running"):
        click.echo(f"Already running at {current['url']} -- opening browser.")
        webbrowser.open(current["url"])
        return

    if _port_in_use(host, port):
        click.secho(
            f"Refusing to start: {host}:{port} is already answering, but not "
            f"as a Scholar GUI we started (no matching state file). A "
            f"different process is bound to this port -- free it, or pass "
            f"--port to use a different one. Not opening the browser.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Starting Scholar GUI server on {host}:{port}...")
    log_path = runtime.path.with_name("gui-serve.log")
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
        if runtime.status().get("running"):
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
def gui_serve(port: int, host: str, db_path: Optional[str]) -> None:
    """Run the Scholar GUI server in the foreground (headless; Ctrl-C to stop).

    \b
    Example:
      $ scitex-scholar gui serve --port 31297
    """
    from .._django import _server

    if _port_in_use(host, port):
        click.secho(
            f"{host}:{port} is already in use by another process -- refusing "
            f"to start (no autoscan). Free the port, or pass --port.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    runtime = _runtime()
    runtime.write_state(os.getpid(), port, host)
    click.echo(f"Scholar GUI serving at http://{host}:{port} (Ctrl-C to stop)")
    try:
        _server.run(port=port, host=host, db_path=db_path, open_browser=False)
    except Exception as exc:
        # Django's `runserver` management command does not reliably raise a
        # bind-failure as a plain OSError (it may print its own error and
        # sys.exit internally) -- the pre-flight `_port_in_use()` check above
        # is the primary guard against double-binds; this broad handler is
        # only a fallback safety net so an unexpected failure exits cleanly
        # instead of leaving a stale state file behind.
        click.secho(f"Scholar GUI server failed: {exc}", fg="red", err=True)
        sys.exit(1)
    finally:
        runtime.clear_state()


@gui.command("status")
@click.option("--json", "as_json", is_flag=True)
def gui_status(as_json: bool) -> None:
    """Report whether the Scholar GUI server is running.

    \b
    Example:
      $ scitex-scholar gui status
    """
    import json as _json

    state = _runtime().status()
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
    runtime = _runtime()
    current = runtime.status()
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
    result = runtime.stop()
    if result.get("stopped"):
        click.echo(f"Stopped (pid {result.get('pid')}).")
    else:
        click.secho(f"Failed to stop: {result.get('error')}", fg="red", err=True)
        sys.exit(1)


# EOF
