#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""URL patterns for the scitex-scholar Django app.

Django is a `[server]`-extra member, so it is not optional AT RUN TIME --
this module IS a urlconf and has no meaning without the framework. It IS
optional for the DISTRIBUTION, so the import is GUARDED and the guard
FAILS LOUDLY rather than substituting anything (see apps.py for why a
silent guard is unacceptable here).
"""

try:
    from django.urls import path
except ImportError as exc:  # django absent -- the [all]-gated GUI capability only
    raise ImportError(
        "scitex_scholar._django.urls needs Django, which is not installed. "
        "Install the optional stack: pip install 'scitex-scholar[all]'"
    ) from exc

from . import views

app_name = "scholar"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/projects", views.project_scope, name="project_scope"),
    path("api/health", views.health, name="health"),
    path("api/search", views.search, name="search"),
    path("api/graph/network", views.graph_network, name="graph_network"),
    path("api/graph/related", views.graph_related, name="graph_related"),
    path("api/graph/paper", views.graph_paper, name="graph_paper"),
    path("api/graph/health", views.graph_health, name="graph_health"),
    path("api/library", views.library_list, name="library_list"),
    path("api/library/enrich", views.library_enrich, name="library_enrich"),
    path("api/library/export", views.library_export, name="library_export"),
    path("api/library/import", views.library_import, name="library_import"),
]

# EOF
