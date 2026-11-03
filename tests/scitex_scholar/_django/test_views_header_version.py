#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The SDK header receives the installed leaf version for diagnostics."""

from __future__ import annotations

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views

def test_header_keeps_version_in_dom():
    # Arrange
    body = _views.index(_RequestFactory().get("/")).content.decode()
    # Act (no Act step: static markup inspection)
    # Assert -- debuggability kept: the mount carries the installed version
    # as a data attribute (the badge renders client-side from it).
    import importlib.metadata

    assert f'data-app-version="{importlib.metadata.version("scitex-scholar")}"' in body


