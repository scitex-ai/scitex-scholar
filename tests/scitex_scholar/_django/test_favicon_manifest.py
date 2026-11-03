"""Real production static-manifest regression for SDK-owned Scholar branding."""

import io
import re

import pytest
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings

from scitex_scholar._django import views


def test_index_context_renders_with_collected_sdk_favicon(tmp_path, monkeypatch):
    # Arrange: use the real public SDK + Scholar static finders and manifest writer.
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path / "projects"))
    root = tmp_path / "collected"
    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    }
    with override_settings(DEBUG=False, STATIC_ROOT=root, STORAGES=storages):
        # Branding resources are the scope: unrelated vendor JS sourcemaps and
        # CSS reference rewriting belong to their own packaging contracts.
        call_command(
            "collectstatic",
            interactive=False,
            verbosity=0,
            ignore=["*.js", "*.css"],
            stdout=io.StringIO(),
        )
        request = RequestFactory().get("/")
        # Act: the old leaf override raises ValueError here with DEBUG=False.
        context = views.index_context(request)
        sdk_url = staticfiles_storage.url("scitex_sdk/ui/img/scitex-favicon.svg")
        # Assert: an actual collected, hashed SDK icon is used by the rendered page.
        body = render_to_string("scitex_sdk/ui/_branding_head.html", context)
        assert sdk_url in body
        assert re.search(r"scitex-favicon\.[a-f0-9]+\.svg", sdk_url)
        assert (root / sdk_url.removeprefix("/static/")).is_file()
        assert "favicon_href" not in context
        with pytest.raises(ValueError, match="manifest entry"):
            staticfiles_storage.url("scholar/img/scitex-favicon-official.svg")
        assert "scholar/img/scitex-favicon-official.svg" not in body
        assert not (root / "scholar/img/scitex-favicon-official.svg").exists()
