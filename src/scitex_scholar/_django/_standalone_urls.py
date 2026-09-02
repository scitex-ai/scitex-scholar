#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Root URLconf for standalone local-dev (`scitex-scholar gui`).

Cloud deployments do not use this -- they include the app's URL module
directly under their own prefix, mirroring how scitex-cloud mounts
`figrecipe._django` under `/figrecipe/`.

STATIC FILES ARE SERVED HERE REGARDLESS OF DEBUG. Django's `runserver` serves
/static/ only while DEBUG=True, and this launcher IS runserver (scitex-app's
`run_standalone` calls it with no `--insecure` passthrough). That coupling is
what kept DJANGO_DEBUG defaulting to "true" -- and with it ALLOWED_HOSTS="*"
on an app with no authentication. Measured 2026-09-02 on the published 1.9.0
wheel under DJANGO_DEBUG=false: GET / -> 200, every /static/ asset -> 404.

`django.contrib.staticfiles.views.serve(insecure=True)` resolves through the
same finders runserver uses (the app's own static/, scitex_ui's, scitex-app's
shell static) and does not consult DEBUG. It is documented as unsuitable for
production, which is exactly right: this urlconf is the LOCAL-DEV launcher and
nothing else routes through it. Hub mounts `urls.py`, not this file.
"""

from django.contrib.staticfiles.views import serve as _serve_static
from django.urls import include, path, re_path

urlpatterns = [
    re_path(r"^static/(?P<path>.*)$", _serve_static, {"insecure": True}),
    path("", include("scitex_scholar._django.urls")),
]

# EOF
