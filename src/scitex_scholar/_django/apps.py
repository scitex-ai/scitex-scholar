#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django AppConfig for the scitex-scholar editor app.

The import below is HARD on purpose, matching `settings.py`'s hard import
of `scitex_ui` and for the same reason -- both are REQUIRED members of the
`server` extra (`scitex-app>=0.5.0`, `scitex-ui>=0.7.1`), so a missing one
is a broken install, not a supported configuration.

It previously read:

    try:    from scitex_app._django import ScitexAppConfig
    except ImportError:  from django.apps import AppConfig as ScitexAppConfig

which is worse than an ordinary swallowed error. It does not merely hide
the failure -- it SUBSTITUTES A DIFFERENT BASE CLASS, so scholar keeps
running and quietly stops being a scitex-app app: every contract the SDK
provides silently stops applying while everything downstream still believes
it is in force. A declaration that cannot be honoured must FAIL, not
evaporate. Ruled by scitex-hub 2026-08-18; scitex-app confirmed it assumes
a hard dependency from scholar's side.
"""

from scitex_app._django import ScitexAppConfig


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
