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
    path("api/search/syntax-help", views.search_syntax_help, name="search_syntax_help"),
    path("api/graph/network", views.graph_network, name="graph_network"),
    path("api/graph/network/multi", views.graph_network_multi, name="graph_network_multi"),
    path("api/graph/network/query", views.graph_network_query, name="graph_network_query"),
    path("api/graph/related", views.graph_related, name="graph_related"),
    path("api/graph/paper", views.graph_paper, name="graph_paper"),
    path("api/graph/health", views.graph_health, name="graph_health"),
    path("api/library", views.library_list, name="library_list"),
    path("api/library/enrich", views.library_enrich, name="library_enrich"),
    path("api/library/export", views.library_export, name="library_export"),
    path("api/library/import", views.library_import, name="library_import"),
    path("api/library/zotero/status", views.zotero_status, name="zotero_status"),
    path("api/library/zotero/collections", views.zotero_collections, name="zotero_collections"),
    path("api/library/zotero/import", views.zotero_import, name="zotero_import"),
    path("api/library/connected-papers/status", views.connected_papers_status, name="connected_papers_status"),
    path("api/library/connected-papers/import", views.connected_papers_import, name="connected_papers_import"),
    path("api/library/save", views.library_save, name="library_save"),
    path("api/library/save-bulk", views.library_save_bulk, name="library_save_bulk"),
    path("api/library/annotate", views.library_annotate, name="library_annotate"),
    path("api/library/remove", views.library_remove, name="library_remove"),
    path("api/library/download-pdfs", views.library_download_pdfs, name="library_download_pdfs"),
    path("api/library/citation", views.library_citation, name="library_citation"),
    path("api/searches/save", views.searches_save, name="searches_save"),
    path("api/searches/list", views.searches_list, name="searches_list"),
    path("api/searches/delete", views.searches_delete, name="searches_delete"),
    path("api/graphs/save", views.graphs_save, name="graphs_save"),
    path("api/graphs/list", views.graphs_list, name="graphs_list"),
    path("api/graphs/delete", views.graphs_delete, name="graphs_delete"),
    path("api/graphs/rename", views.graphs_rename, name="graphs_rename"),
]

# EOF
