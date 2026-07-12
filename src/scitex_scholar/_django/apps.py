#!/usr/bin/env python3
# -*- coding: utf-8 -*-
try:
    from scitex_app._django import ScitexAppConfig
except ImportError:
    from django.apps import AppConfig as ScitexAppConfig


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
