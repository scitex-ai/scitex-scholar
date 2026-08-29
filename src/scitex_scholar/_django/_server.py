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
    if host not in ("127.0.0.1", "localhost", "0.0.0.0"):
        _configured = os.environ.get("SCITEX_SCHOLAR_ALLOWED_HOSTS", "")
        _hosts = [h.strip() for h in _configured.split(",") if h.strip()]
        if host not in _hosts:
            _hosts.append(host)
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
