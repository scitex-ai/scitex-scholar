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
]

# EOF
