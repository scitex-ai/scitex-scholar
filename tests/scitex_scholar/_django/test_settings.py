#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the standalone Django settings module.

Mirrors `scitex_scholar/_django/settings.py` (PS-204: test file per src file).
"""

from __future__ import annotations

import importlib.util

from scitex_scholar._django import settings

_SCITEX_UI_INSTALLED = importlib.util.find_spec("scitex_ui") is not None


def test_element_inspector_middleware_present_when_scitex_ui_installed():
    # Arrange
    target = "scitex_ui.middleware.ElementInspectorMiddleware"
    # Act
    has_middleware = target in settings.MIDDLEWARE
    # Assert
    assert has_middleware == _SCITEX_UI_INSTALLED
