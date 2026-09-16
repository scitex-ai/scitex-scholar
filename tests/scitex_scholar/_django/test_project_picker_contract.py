#!/usr/bin/env python3
"""Scholar-owned header and shared project-picker contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import scitex_ui
import tomllib
from django.test import RequestFactory, override_settings
from scitex_ui.project_scope import LocalProjectProvider

from scitex_scholar._django import views

_DJANGO_DIR = Path(views.__file__).parent
_TEMPLATE = _DJANGO_DIR / "templates" / "scholar" / "scholar.html"
_LAYOUT = _DJANGO_DIR / "static" / "scholar" / "css" / "_partials" / "_layout.css"
_PROJECT_SELECTOR_CSS = (
    Path(scitex_ui.__file__).parent
    / "static"
    / "scitex_ui"
    / "css"
    / "app"
    / "project-selector.css"
)
_REPO_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file()
)


def _render(path: str = "/") -> str:
    return views.index(RequestFactory().get(path)).content.decode()


def test_standalone_uses_scitex_ui_local_project_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    with override_settings(SCITEX_PROJECT_PROVIDER=""):
        provider = views._project_provider(RequestFactory().get("/"))
    assert type(provider) is LocalProjectProvider


def test_mounted_host_provider_takes_precedence(monkeypatch, tmp_path):
    host_provider = object()
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(views, "host_project_provider", lambda: host_provider)
    assert views._project_provider(RequestFactory().get("/")) is host_provider


def test_standalone_project_endpoint_lists_local_projects(monkeypatch, tmp_path):
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "Beta").mkdir()
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    with override_settings(SCITEX_PROJECT_PROVIDER=""):
        response = views.project_scope(RequestFactory().get("/api/projects"))
    payload = json.loads(response.content)
    assert [project["id"] for project in payload["projects"]] == ["Alpha", "Beta"]


def test_index_renders_one_picker_in_canonical_scholar_header(monkeypatch, tmp_path):
    (tmp_path / "Alpha").mkdir()
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    with override_settings(
        SCITEX_PROJECT_PROVIDER="",
        SCITEX_PROJECT_PROVIDER_URL="/api/projects",
    ):
        html = _render("/?project=Alpha")
    assert html.count("data-stx-project-picker") == 1


def test_index_picker_navigates_with_project_query(monkeypatch, tmp_path):
    (tmp_path / "Alpha").mkdir()
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    with override_settings(
        SCITEX_PROJECT_PROVIDER="",
        SCITEX_PROJECT_PROVIDER_URL="/api/projects",
    ):
        html = _render("/?project=Alpha")
    assert 'data-current="Alpha" data-navigate="?project={id}"' in html


def test_host_mount_supplies_picker_provider_url(monkeypatch, tmp_path):
    monkeypatch.setenv("SCITEX_SCHOLAR_PROJECTS_DIR", str(tmp_path))
    with override_settings(
        SCITEX_PROJECT_PROVIDER="",
        SCITEX_PROJECT_PROVIDER_URL="/host/api/project-scope/",
    ):
        html = _render("/")
    assert 'data-provider-url="/host/api/project-scope/"' in html


def test_header_source_places_picker_after_identity_before_content():
    source = _TEMPLATE.read_text()
    identity = source.index('class="stx-app-header__identity"')
    picker = source.index('class="stx-app-header__slot--project-selector"')
    content = source.index('class="app-container"')
    assert identity < picker < content


def test_manifest_declares_project_scope():
    manifest = json.loads((_DJANGO_DIR / "manifest.json").read_text())
    assert manifest["scope"] == "project"


def test_server_extra_requires_header_slot_capable_scitex_ui():
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    requirements = config["project"]["optional-dependencies"]["server"]
    assert "scitex-ui>=0.22.0" in requirements


def test_390px_header_wraps_picker_without_horizontal_overflow():
    css = _LAYOUT.read_text()
    mobile = css.split("@media (max-width: 600px)", 1)[1]
    header = re.search(r"\.stx-app-header\s*\{[^}]*flex-wrap:\s*wrap[^}]*\}", mobile)
    slot = re.search(
        r"\.stx-app-header__slot--project-selector\s*\{[^}]*width:\s*100%[^}]*\}",
        mobile,
    )
    assert header is not None and slot is not None


def test_desktop_header_uses_canonical_left_picker_slot():
    css = _LAYOUT.read_text()
    header = re.search(r"\.stx-app-header\s*\{[^}]*display:\s*flex[^}]*\}", css)
    assert header is not None


def test_shared_desktop_slot_pins_picker_left_before_actions():
    css = _PROJECT_SELECTOR_CSS.read_text()
    slot = re.search(
        r"\.stx-app-header__slot--project-selector\s*\{"
        r"[^}]*order:\s*1[^}]*margin-left:\s*0[^}]*margin-right:\s*auto[^}]*\}",
        css,
    )
    assert slot is not None


def test_shared_picker_has_44px_390px_touch_target():
    css = _PROJECT_SELECTOR_CSS.read_text()
    mobile = css.split("@media (max-width: 600px), (pointer: coarse)", 1)[1]
    assert re.search(
        r"\.stx-app-project-selector__trigger[^}]*height:\s*44px",
        mobile,
    )
