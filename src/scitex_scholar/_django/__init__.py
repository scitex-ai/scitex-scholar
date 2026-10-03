#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django app exposing the scitex-scholar citation-graph GUI.

Mirrors the figrecipe/_django and scitex_writer/_django pattern so a
single canonical implementation drives the standalone GUI
(`scitex-scholar gui`). Scholar has no per-invocation project/working-dir
concept -- it is a single shared CrossRef-DB browser + citation-graph
viewer.
"""

default_app_config = "scitex_scholar._django.apps.ScholarEditorConfig"

# Keep discovery lazy: the host resolves this leaf-owned context builder
# only when rendering the existing Scholar page.
context_builder = "scitex_scholar._django.views.index_context"

__all__ = ["default_app_config", "context_builder"]

# EOF
