#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone local-dev launcher for the Scholar GUI.

Delegates to `scitex_app.embed.run_standalone`, which pre-wires
scitex-ui static assets + the workspace shell so the same local server
looks like scitex.ai/apps/scholar.

Cloud deployments do NOT use this -- they mount `scitex_scholar._django.urls`
into their own Django project.

Simpler than scitex-writer's `_server.py`: scholar has no per-invocation
project directory / working-dir concept, so `run()` takes no
`project_dir` parameter.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from typing import Optional

# The single source of truth for scholar's GUI port; `_cli/gui.py` imports
# it from here rather than restating the literal (they used to "just agree
# on 31297", which is a coincidence maintained by hand, not a constant).
DEFAULT_PORT = 31297

_LOOPBACK = ("127.0.0.1", "localhost")
_BIND_ALL = "0.0.0.0"


def _interface_ipv4_addresses() -> list[str]:
    """Every IPv4 address assigned to a network interface on this machine.

    Read from the INTERFACES (SIOCGIFADDR per `socket.if_nameindex()` entry),
    not from name resolution. `getaddrinfo(gethostname())` was the first
    attempt and it FAILED THE LIVE CHECK while passing the unit test: inside a
    container the hostname resolves to an address that is not the LAN
    interface, so `--host 0.0.0.0` still answered 400 to the real address.
    The unit test had only asserted the hostname was present -- it could not
    fail for the case that mattered. Interfaces cannot lie about which
    addresses they hold. Linux/macOS ioctl; returns [] where unavailable.
    """
    import socket

    try:
        import fcntl
        import struct
    except ImportError:  # not a POSIX platform
        return []

    _SIOCGIFADDR = 0x8915
    found: list[str] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for _, name in socket.if_nameindex():
            try:
                packed = fcntl.ioctl(
                    s.fileno(),
                    _SIOCGIFADDR,
                    struct.pack("256s", name[:15].encode()),
                )
            except OSError:
                continue  # interface with no IPv4 address
            addr = socket.inet_ntoa(packed[20:24])
            if not addr.startswith("127.") and addr not in found:
                found.append(addr)
    return found


def _local_addresses() -> list[str]:
    """This machine's hostname plus every IPv4 address its interfaces hold.

    Used only for the 0.0.0.0 bind. Loopback is excluded because settings.py
    already lists it.
    """
    import socket

    found: list[str] = []
    hostname = socket.gethostname()
    if hostname:
        found.append(hostname)
    found.extend(a for a in _interface_ipv4_addresses() if a not in found)
    return found


def _hosts_to_allow(host: str) -> list[str]:
    """What a given ``--host`` bind implies for ALLOWED_HOSTS. Pure function.

    Binding to an address IS the statement that you intend to be reached on
    it, so contribute it rather than making the caller set an env var to
    permit what they already asked for:

        127.0.0.1 / localhost   -> []            settings.py lists loopback
        0.0.0.0                 -> hostname + this machine's interface addresses
        anything else           -> [host]

    The 0.0.0.0 rule is what makes DEBUG=False the safe default WITHOUT
    reintroducing the bug #126 fixed: a bind-all server receives requests whose
    Host header is the real interface address, and "0.0.0.0" in ALLOWED_HOSTS
    never matches that. Measured 2026-09-02 on the published 1.9.0 wheel:
    `--host 0.0.0.0` with DJANGO_DEBUG=false answered 400 to every real
    address while loopback answered 200.
    """
    if host in _LOOPBACK:
        return []
    if host == _BIND_ALL:
        return _local_addresses()
    return [host]


def run(
    port: int = DEFAULT_PORT,
    host: str = "127.0.0.1",
    api_url: Optional[str] = None,
    open_browser: bool = True,
    desktop: bool = False,
    hot_reload: bool = False,
) -> None:
    """Launch the Django Scholar GUI server locally on exactly ``port``.

    Tries `scitex_app.embed.run_standalone` first (gets the full
    workspace shell from scitex-ui). Falls back to a bare runserver
    bootstrap if scitex-app is not installed.

    The requested port is bound as given: when it is already in use the
    server fails instead of drifting to the next free port.
    """
    if api_url:
        # Write the canonical name; resolve_env reads this one first.
        os.environ["SCITEX_SCHOLAR_CROSSREF_LOCAL_API_URL"] = api_url

    # Serving on a non-loopback address requires that address in ALLOWED_HOSTS,
    # or Django answers 400 to every request while the startup banner still
    # prints a URL that looks fine. Binding to an address IS the statement that
    # you intend to be reached on it, so contribute it rather than making the
    # caller set an env var to permit what they already asked for.
    #
    # settings.py reads this variable and APPENDS, so an explicitly configured
    # list (proxy DNS name, MagicDNS name) survives alongside the bind address.
    _contributed = _hosts_to_allow(host)
    if _contributed:
        _configured = os.environ.get("SCITEX_SCHOLAR_ALLOWED_HOSTS", "")
        _hosts = [h.strip() for h in _configured.split(",") if h.strip()]
        for _h in _contributed:
            if _h not in _hosts:
                _hosts.append(_h)
        os.environ["SCITEX_SCHOLAR_ALLOWED_HOSTS"] = ",".join(_hosts)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scitex_scholar._django.settings")

    print(f"SciTeX Scholar GUI: http://{host}:{port}")
    print("Press Ctrl+C to stop")

    # ONLY the import is guarded. Wrapping `django.setup()`, the migration,
    # or the `run_standalone` CALL in this try would make a genuine
    # ImportError from deep inside the app indistinguishable from "scitex-app
    # is not installed" -- and would silently degrade a broken install to bare
    # Django instead of reporting it.
    try:
        from scitex_app.embed import run_standalone
    except ImportError:
        run_standalone = None
        print(
            "Note: scitex-app is not installed, so the workspace shell is "
            "unavailable; serving bare Django instead.\n"
            "      Get it with: pip install 'scitex-scholar[server]'"
        )

    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", "--run-syncdb", verbosity=0)

    if run_standalone is not None:
        run_standalone(
            app_module="scitex_scholar._django",
            port=port,
            host=host,
            open_browser=open_browser,
            hot_reload=hot_reload,
            desktop=desktop,
        )
        return

    # Degraded path: bare Django, no workspace shell (reason printed above).

    if open_browser and not desktop:
        threading.Timer(1.0, webbrowser.open, args=[f"http://{host}:{port}"]).start()

    noreload = [] if hot_reload else ["--noreload"]
    call_command("runserver", f"{host}:{port}", *noreload)


# EOF
