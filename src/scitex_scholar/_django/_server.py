#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone local-dev launcher for the Scholar GUI.

Delegates to `scitex_app._standalone.run_standalone`, which pre-wires
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

# Scholar has no shared `_core` module for this constant (unlike writer's
# `_core._gui_runtime.DEFAULT_PORT`); both `_cli/gui.py` and this module
# just agree on the literal port 31297.
DEFAULT_PORT = 31297


def run(
    port: int = DEFAULT_PORT,
    host: str = "127.0.0.1",
    db_path: Optional[str] = None,
    open_browser: bool = True,
    desktop: bool = False,
    hot_reload: bool = False,
) -> None:
    """Launch the Django Scholar GUI server locally on exactly ``port``.

    Tries `scitex_app._standalone.run_standalone` first (gets the full
    workspace shell from scitex-ui). Falls back to a bare runserver
    bootstrap if scitex-app is not installed.

    The requested port is bound as given: when it is already in use the
    server fails instead of drifting to the next free port.
    """
    if db_path:
        os.environ["CROSSREF_DB_PATH"] = db_path
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scitex_scholar._django.settings")

    print(f"SciTeX Scholar GUI: http://{host}:{port}")
    print("Press Ctrl+C to stop")

    try:
        import django

        django.setup()

        from django.core.management import call_command

        call_command("migrate", "--run-syncdb", verbosity=0)

        from scitex_app._standalone import run_standalone

        run_standalone(
            app_module="scitex_scholar._django",
            port=port,
            host=host,
            open_browser=open_browser,
            hot_reload=hot_reload,
            desktop=desktop,
        )
        return
    except ImportError:
        pass

    # Fallback: no scitex-app available, run bare Django
    import django

    django.setup()
    from django.core.management import call_command

    if open_browser and not desktop:
        threading.Timer(1.0, webbrowser.open, args=[f"http://{host}:{port}"]).start()

    noreload = [] if hot_reload else ["--noreload"]
    call_command("runserver", f"{host}:{port}", *noreload)


# EOF
