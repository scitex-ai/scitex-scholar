"""Real production static-manifest regression for SDK-owned Scholar branding."""

import io
import os
import re

import pytest
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings

from scitex_scholar._django import views


@pytest.fixture(scope="module")
def collected_branding(tmp_path_factory):
    root = tmp_path_factory.mktemp("scholar-branding")
    previous = os.environ.get("SCITEX_SCHOLAR_PROJECTS_DIR")
    os.environ["SCITEX_SCHOLAR_PROJECTS_DIR"] = str(root / "projects")
    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    }
    try:
        with override_settings(DEBUG=False, STATIC_ROOT=root, STORAGES=storages):
            # This regression concerns real branding resources. Vendor JS
            # sourcemaps and CSS rewriting have separate packaging contracts.
            call_command(
                "collectstatic",
                interactive=False,
                verbosity=0,
                ignore=["*.js", "*.css"],
                stdout=io.StringIO(),
            )
            context = views.index_context(RequestFactory().get("/"))
            yield {
                "root": root,
                "context": context,
                "body": render_to_string("scitex_sdk/ui/_branding_head.html", context),
                "url": staticfiles_storage.url("scitex_sdk/ui/img/scitex-favicon.svg"),
            }
    finally:
        if previous is None:
            os.environ.pop("SCITEX_SCHOLAR_PROJECTS_DIR", None)
        else:
            os.environ["SCITEX_SCHOLAR_PROJECTS_DIR"] = previous


def test_context_defers_favicon_to_sdk(collected_branding):
    # Arrange
    context = collected_branding["context"]
    # Act
    overridden = "favicon_href" in context
    # Assert
    assert not overridden


def test_branding_renders_collected_sdk_url(collected_branding):
    # Arrange
    body = collected_branding["body"]
    # Act
    present = collected_branding["url"] in body
    # Assert
    assert present


def test_sdk_favicon_url_is_content_hashed(collected_branding):
    # Arrange
    url = collected_branding["url"]
    # Act
    hashed = re.search(r"scitex-favicon\.[a-f0-9]+\.svg", url)
    # Assert
    assert hashed


def test_sdk_favicon_has_actual_collected_bytes(collected_branding):
    # Arrange
    root, url = collected_branding["root"], collected_branding["url"]
    # Act
    exists = (root / url.removeprefix("/static/")).is_file()
    # Assert
    assert exists


def test_strict_manifest_refuses_removed_leaf_icon(collected_branding):
    # Arrange
    missing = "scholar/img/scitex-favicon-official.svg"
    # Act / Assert
    with pytest.raises(ValueError, match="manifest entry"):
        staticfiles_storage.url(missing)


def test_branding_does_not_render_removed_leaf_icon(collected_branding):
    # Arrange
    body = collected_branding["body"]
    # Act
    legacy = "scholar/img/scitex-favicon-official.svg" in body
    # Assert
    assert not legacy
