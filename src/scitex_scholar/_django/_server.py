#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone local-dev launcher for the Scholar GUI.

Delegates to `scitex_app.embed.run_standalone`, which pre-wires
scitex-ui static assets + the workspace shell so the same local server
looks like scitex.ai/apps/scholar. There is no bare-Django fallback
(retired 2026-09-03, see the Removed entry in CHANGELOG), because a
fallback that silently drops the shell AND the ALLOWED_HOSTS derivation
is a second, quieter way to break.

scitex-app is an OPTIONAL dependency of the DISTRIBUTION (`[server]`), not
of this MODULE. `_cli/gui.py` imports `DEFAULT_PORT` from here at module
top, so this file sits on the console-script launch path and must import
with or without the GUI stack installed. The capability is still not
optional at RUN time: `run()` refuses with the extra's name rather than
falling back to a half-wired server (see the guards below).

Cloud deployments do NOT use this -- they mount `scitex_scholar._django.urls`
into their own Django project.

Simpler than scitex-writer's `_server.py`: scholar has no per-invocation
project directory / working-dir concept, so `run()` takes no
`project_dir` parameter.
"""

from __future__ import annotations

import os
from typing import Optional

import scitex_logging as slogging

console = slogging.getConsole(__name__)

# The single source of truth for scholar's GUI port; `_cli/gui.py` imports
# it from here rather than restating the literal (they used to "just agree
# on 31297", which is a coincidence maintained by hand, not a constant).
DEFAULT_PORT = 31297

# The ONE install line every [all]-gated GUI-capability refusal names, so the
# CLI notice and the in-module refusals cannot drift apart.
ALL_EXTRA_HINT = "pip install 'scitex-scholar[all]'"

# `hosts_to_allow` lived here first (#137) and was copied verbatim into
# scitex-app, which made it the fleet's single implementation and gave it a
# PUBLIC name in 0.11.0. The copy is gone; the import is the whole point.
#
# GUARDED (2026-09-20). It used to be a hard import, on the reasoning that
# the server extra requires scitex-app so a missing one is a broken install
# -- true of `gui serve`, false of THIS MODULE, which the console script
# imports at launch (`_cli/gui.py` -> `DEFAULT_PORT`). An unguarded import
# here made `scitex-scholar --version` fail on a bare install.
#
# The guard is LOUD, not a fallback: the sentinels stay None and every RUN
# path that needs them refuses by name. Nothing is silently substituted --
# which is the failure mode the retired try/except base-class swap had.
try:
    from scitex_app import hosts_to_allow
    from scitex_app.embed import run_standalone
except ImportError:  # scitex-app absent -- the [server] capability only
    hosts_to_allow = None  # type: ignore[assignment]
    run_standalone = None  # type: ignore[assignment]


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
    # Refuse BEFORE touching the environment or printing a URL. The CLI
    # (`_cli/gui.py::_embed`) normally gates this first; this is the second
    # gate, so an in-process `_server.run(...)` caller gets the same
    # actionable sentence instead of an AttributeError on a None sentinel.
    if run_standalone is None or hosts_to_allow is None:
        raise ImportError(
            "The Scholar GUI server needs scitex-app, which is not installed. "
            f"Install the optional stack: {ALL_EXTRA_HINT}"
        )

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

    console.info(f"SciTeX Scholar GUI: http://{host}:{port}")
    console.info("Press Ctrl+C to stop")

    try:
        import django
        from django.core.management import call_command
    except ImportError as exc:  # the [all] GUI stack, second member
        raise ImportError(
            "The Scholar GUI server needs Django, which is not installed. "
            f"Install the optional stack: {ALL_EXTRA_HINT}"
        ) from exc

    django.setup()

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
