#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""URL patterns for the scitex-scholar Django app."""

from django.urls import path

from . import views

app_name = "scholar"

urlpatterns = [
    path("", views.index, name="index"),
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
