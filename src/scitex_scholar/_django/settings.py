#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal standalone Django settings for `scitex-scholar gui`.

Used only by the standalone launcher; cloud deployments ignore this
module and mount `scitex_scholar._django.urls` under their own prefix.

Mirrors the `scitex_writer._django.settings` pattern: bare-minimum
installed apps, optional `scitex_ui` for the shared workspace shell, and
a SQLite database so any future models work out of the box.

`CROSSREF_DB_PATH` is resolved ONCE here at settings-load time (mirroring
how the Flask `create_app()` resolved it once too) so `views.py` reads a
plain setting instead of re-probing the filesystem on every request.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

from ._db import find_crossref_db

BASE_DIR = Path(__file__).resolve().parent

# Fleet env-var convention is SCITEX_SCHOLAR_<X>.
SECRET_KEY = os.environ.get("SCITEX_SCHOLAR_DJANGO_SECRET") or secrets.token_urlsafe(32)
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0", "testserver"]

# "hub" | "standalone" -- the browser tab alone must distinguish the two
# (fleet convention; scitex-hub reads the same setting and defaults to
# "hub"). These settings only boot the STANDALONE server
# (`scitex-scholar gui`), so standalone is the default here.
SCITEX_APP_MODE = os.environ.get("SCITEX_APP_MODE", "standalone")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "scitex_scholar._django.apps.ScholarEditorConfig",
]

# Optional: scitex-ui supplies the workspace shell (template + CSS/JS assets)
try:
    import scitex_ui  # noqa: F401

    INSTALLED_APPS.append("scitex_ui")
except ImportError:
    pass

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "scitex_scholar._django._standalone_urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# SQLite lives in the temp dir so local runs don't pollute the project
_DB_DIR = Path(tempfile.gettempdir()) / "scitex_scholar"
_DB_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(_DB_DIR / "db.sqlite3"),
    }
}

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# Resolved once here (mirrors the Flask create_app() resolve-once
# behaviour); views.py reads this setting rather than re-probing.
CROSSREF_DB_PATH = find_crossref_db()

# EOF
