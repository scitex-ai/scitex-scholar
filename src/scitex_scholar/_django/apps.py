#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django AppConfig for the scitex-scholar editor app.

`scitex_scholar._django.apps` only exists inside the `server` extra's world:
the module IS the AppConfig a running Django project loads. scitex-app is
therefore not optional AT RUN TIME -- but it IS optional for the
distribution (a bare `pip install scitex-scholar` must not pull Django), so
the import is GUARDED and the guard FAILS LOUDLY.

It previously read:

    try:    from scitex_app._django import ScitexAppConfig
    except ImportError:  from django.apps import AppConfig as ScitexAppConfig

which is worse than an ordinary swallowed error. It does not merely hide
the failure -- it SUBSTITUTES A DIFFERENT BASE CLASS, so scholar keeps
running and quietly stops being a scitex-app app: every contract the SDK
provides silently stops applying while everything downstream still believes
it is in force. A declaration that cannot be honoured must FAIL, not
evaporate. Ruled by scitex-hub 2026-08-18.

The guard below honours that ruling: the `except` re-raises with the extra
to install, so the failure is as legible as the hard import was and it
still cannot be mistaken for a working install.
"""

try:
    from scitex_app._django import ScitexAppConfig
except ImportError as exc:  # scitex-app absent -- the [server] capability only
    raise ImportError(
        "scitex_scholar._django needs scitex-app, which is not installed. "
        "Install the server extra: pip install 'scitex-scholar[server]'"
    ) from exc


class ScholarEditorConfig(ScitexAppConfig):
    # label="scholar_editor" (not "scholar"/"scholar_app") -- scitex-hub
    # already has an unrelated Django app labeled "scholar_app" at
    # apps/workspace/scholar_app/ (its own models/migrations, zero
    # dependency on this pip package). A distinct label avoids any future
    # app-registry collision if the two ever coexist in one Django process.
    name = "scitex_scholar._django"
    label = "scholar_editor"
    verbose_name = "SciTeX Scholar"


# EOF
