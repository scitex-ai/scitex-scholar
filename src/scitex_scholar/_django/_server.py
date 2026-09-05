#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone local-dev launcher for the Scholar GUI.

Delegates to `scitex_app.embed.run_standalone`, which pre-wires
scitex-ui static assets + the workspace shell so the same local server
looks like scitex.ai/apps/scholar. scitex-app is a HARD dependency of the
server extra: there is no bare-Django fallback any more (retired 2026-09-03,
see the Removed entry in CHANGELOG), because a fallback that silently drops
the shell AND the ALLOWED_HOSTS derivation is a second, quieter way to break.

Cloud deployments do NOT use this -- they mount `scitex_scholar._django.urls`
into their own Django project.

Simpler than scitex-writer's `_server.py`: scholar has no per-invocation
project directory / working-dir concept, so `run()` takes no
`project_dir` parameter.
"""

from __future__ import annotations

import os
from typing import Optional

# The single source of truth for scholar's GUI port; `_cli/gui.py` imports
# it from here rather than restating the literal (they used to "just agree
# on 31297", which is a coincidence maintained by hand, not a constant).
DEFAULT_PORT = 31297

# `hosts_to_allow` lived here first (#137) and was copied verbatim into
# scitex-app, which made it the fleet's single implementation and gave it a
# PUBLIC name in 0.11.0. The copy is gone; the import is the whole point.
# Hard import on purpose: the server extra requires scitex-app, and settings.py
# already hard-imports scitex_ui by the same reasoning -- fail where the cause
# is legible, not three layers later as a 400 nobody can explain.
from scitex_app import hosts_to_allow
from scitex_app.embed import run_standalone

def run(
    port: int = DEFAULT_PORT,
    host: str = "127.0.0.1",
    api_url: Optional[str] = None,
    open_browser: bool = True,
    desktop: bool = False,
    hot_reload: bool = False,
) -> None:
    """Launch the Django Scholar GUI server locally on exactly ``port``.

    Runs through `scitex_app.embed.run_standalone` (the full workspace
    shell from scitex-ui). No fallback: scitex-app is required.

    The requested port is bound as given: when it is already in use the
    server fails instead of drifting to the next free port.
    """
    if api_url:
        # Write the canonical name; resolve_env reads this one first.
        os.environ["SCITEX_SCHOLAR_CROSSREF_API_URL"] = api_url

    # Serving on a non-loopback address requires that address in ALLOWED_HOSTS,
    # or Django answers 400 to every request while the startup banner still
    # prints a URL that looks fine. Binding to an address IS the statement that
    # you intend to be reached on it, so contribute it rather than making the
    # caller set an env var to permit what they already asked for.
    #
    # settings.py reads this variable and APPENDS, so an explicitly configured
    # list (proxy DNS name, MagicDNS name) survives alongside the bind address.
    _contributed = hosts_to_allow(host)
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

    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", "--run-syncdb", verbosity=0)

    run_standalone(
        app_module="scitex_scholar._django",
        port=port,
        host=host,
        open_browser=open_browser,
        hot_reload=hot_reload,
        desktop=desktop,
    )


# EOF
