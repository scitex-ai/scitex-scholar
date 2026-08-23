#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Django test bootstrap -- configures settings once for all tests in this pkg.

Mirrors `scitex_writer/tests/_django/conftest.py`'s bare `django.setup()`
bootstrap (no `pytest-django` dependency needed): scholar has no
per-invocation project/working-dir concept, so there is nothing else to
fixture here.
"""

from __future__ import annotations

import os

import django
from django.conf import settings


def _init_django() -> None:
    if settings.configured:
        return
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scitex_scholar._django.settings")
    django.setup()


_init_django()

# EOF
