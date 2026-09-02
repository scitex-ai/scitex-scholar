#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal standalone Django settings for `scitex-scholar gui`.

Used only by the standalone launcher; cloud deployments ignore this
module and mount `scitex_scholar._django.urls` under their own prefix.

Mirrors the `scitex_writer._django.settings` pattern: bare-minimum
installed apps, optional `scitex_ui` for the shared workspace shell, and
the fleet PostgreSQL so any future models work out of the box.

`CROSSREF_API_URL` is resolved ONCE here at settings-load time (mirroring
how the Flask `create_app()` resolved its backend once too) so `views.py`
reads a plain setting instead of re-probing on every request.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from ._db import find_crossref_api_url

BASE_DIR = Path(__file__).resolve().parent

# Fleet env-var convention is SCITEX_SCHOLAR_<X>.
SECRET_KEY = os.environ.get("SCITEX_SCHOLAR_DJANGO_SECRET") or secrets.token_urlsafe(32)
# DEBUG DEFAULTS TO FALSE (2026-09-02). It defaulted to "true" until then, which
# made the PERMISSIVE branch below the DEFAULT branch: every `gui serve` that
# forgot to set DJANGO_DEBUG=false was ALLOWED_HOSTS="*" on an app with no
# authentication of its own. The reason it was left that way -- DEBUG=False
# stops `runserver` serving static files -- is answered in _standalone_urls.py,
# which serves them through the staticfiles finders regardless of DEBUG.
# Measured before flipping: under DJANGO_DEBUG=false the page returned 200 and
# every /static/ asset returned 404; after the urlconf change, both are 200.
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
# ALLOWED_HOSTS SWITCHES ON DEBUG (operator ruling, 2026-08-23).
#
# THE BUG THIS REPLACES: the list used to be the hardcoded loopback-only
# ["127.0.0.1", "localhost", "0.0.0.0", "testserver"] with no way to extend it,
# so `gui serve --host <addr>` was unreachable by construction -- the server
# started, printed its URL, and answered 400 Bad Request to every caller with
# nothing in the banner to suggest ALLOWED_HOSTS was the reason. All four leaves
# (storage / writer / figrecipe / scholar) carried the same copied list.
#
# DEBUG=True  -> "*". Explicit opt-in for development only.
# DEBUG=False -> loopback + whatever `--host` contributes (see _server.py:
#                a specific address contributes itself; 0.0.0.0 contributes
#                this machine's hostname and interface addresses, because
#                binding every interface IS the statement that you intend to
#                be reached on any of them) + SCITEX_SCHOLAR_ALLOWED_HOSTS.
#
# Without the 0.0.0.0 rule the default flip would have REINTRODUCED the bug
# this block replaced: `--host 0.0.0.0` bound fine and answered 400 to every
# real address, measured 2026-09-02 on the published 1.9.0 wheel.
if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0", "testserver"]
    # Deployment cases the bind address alone does not cover: a reverse proxy
    # passing a DNS name, a tailnet MagicDNS name, several addresses at once.
    # Comma-separated; SCITEX_SCHOLAR_ is the fleet prefix convention (#109).
    # `--host` also contributes its own address here (see _server.py).
    _extra_hosts = os.environ.get("SCITEX_SCHOLAR_ALLOWED_HOSTS", "")
    ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(",") if h.strip()]

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

# scitex-ui supplies the shared SciTeX branding partial that
# `scholar.html` includes in its <head>. It is a REQUIRED member of the
# `server` extra (alongside django itself), so this import is hard on
# purpose: a `try/except ImportError` here would swallow a broken install
# and resurface it later as a TemplateDoesNotExist pointing at scitex-ui's
# template -- sending the reader to the wrong package. Fail at import time,
# where the cause is legible.
import scitex_ui  # noqa: F401

INSTALLED_APPS.append("scitex_ui")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Alt+I / Ctrl+I visual debugging overlay.
    "scitex_ui.middleware.ElementInspectorMiddleware",
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

# DJANGO'S ORM POINTS AT THE FLEET POSTGRESQL.
#
# This app declares no models of its own today, so nothing here opens a
# connection during a normal request -- but the setting still has to name a
# real, WRITABLE cluster, because the first model that appears would
# otherwise inherit whatever the default was.
#
# `scitex-primary:55432` is the writable primary. Every per-host loopback on
# 55432 is a READ-ONLY REPLICA of the same cluster and refuses writes, so
# `127.0.0.1` must never be the default here: it would work for reads and
# fail only on the first write, which is the worst possible time to find out.
#
# USER/PASSWORD default to empty, which makes libpq connect as the OS user
# and consult ~/.pgpass -- the fleet's normal path. Override any field with
# the matching SCITEX_SCHOLAR_DB_* environment variable.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("SCITEX_SCHOLAR_DB_NAME", "scitex"),
        "HOST": os.environ.get("SCITEX_SCHOLAR_DB_HOST", "scitex-primary"),
        "PORT": os.environ.get("SCITEX_SCHOLAR_DB_PORT", "55432"),
        "USER": os.environ.get("SCITEX_SCHOLAR_DB_USER", ""),
        "PASSWORD": os.environ.get("SCITEX_SCHOLAR_DB_PASSWORD", ""),
    }
}

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# Resolved once here (mirrors the Flask create_app() resolve-once
# behaviour); views.py reads this setting rather than re-probing.
CROSSREF_API_URL = find_crossref_api_url()

# EOF
