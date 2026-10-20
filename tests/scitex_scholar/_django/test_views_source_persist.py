#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U3 (old-direct unification): source-selection persistence.

KEEP: hub `save_source_preferences` semantics -- visitor gets a session
note (client keeps localStorage), a file-user gets persistence; invalid
JSON fails closed (400). CHANGE: persistence is a `source-preferences.json`
under the request's user-scoped root instead of the `UserPreference`
model (leaf stays off hub DB). VERIFY: pins round-trip both paths;
`?sources=` echo unchanged (covered by test_views_search_sources.py).
"""

from __future__ import annotations

import json as _json
from pathlib import Path as _Path
from types import SimpleNamespace as _NS

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import urls as _urls
from scitex_scholar._django import views as _views


def _post(body, user=None, root=None):
    request = _RequestFactory().post(
        "/api/preferences/sources", data=body, content_type="application/json"
    )
    if user is not None:
        request.user = user
    if root is not None:
        request.scholar_library_root = root
    return request


def _visitor():
    return _NS(username="visitor", is_authenticated=False)


def _file_user(name="alice"):
    return _NS(username=name, is_authenticated=True)


def test_visitor_post_gets_session_note_and_stores_nothing(tmp_path):
    # Arrange -- hub parity: visitors are noted, persistence is theirs.
    # Act
    resp = _views.preferences_sources(_post('{"sources": ["pubmed"]}', _visitor(), tmp_path / "v"))
    # Assert -- one tuple compare (STX-TQ007).
    assert (_json.loads(resp.content)["saved_to"], (tmp_path / "v").exists()) == ("session", False)


def test_file_user_post_persists_to_user_root_and_round_trips(tmp_path):
    # Arrange
    root = tmp_path / "alice"
    sources = ["pubmed", "arxiv"]
    # Act
    saved = _views.preferences_sources(_post(_json.dumps({"sources": sources}), _file_user(), root))
    request = _RequestFactory().get("/api/preferences/sources")
    request.user = _file_user()
    request.scholar_library_root = root
    listed = _views.preferences_sources(request)
    # Assert -- saved flag, stored file content, and GET echo agree.
    assert (
        _json.loads(saved.content)["saved_to"],
        _json.loads((root / "source-preferences.json").read_text())["sources"],
        _json.loads(listed.content)["sources"],
    ) == ("user-root", sources, sources)


def test_list_defaults_to_empty_sources_for_unknown_user(tmp_path):
    # Arrange
    request = _RequestFactory().get("/api/preferences/sources")
    request.user = _file_user("newbie")
    request.scholar_library_root = tmp_path / "newbie"
    # Act
    resp = _views.preferences_sources(request)
    # Assert
    assert (resp.status_code, _json.loads(resp.content)["sources"]) == (200, {})


def test_malformed_json_fails_closed_with_400():
    # Arrange
    request = _RequestFactory().post(
        "/api/preferences/sources", data="{not-json", content_type="application/json"
    )
    # Act
    resp = _views.preferences_sources(request)
    # Assert
    assert (resp.status_code, _json.loads(resp.content)["status"]) == (400, "error")


def test_preferences_sources_route_is_registered_flat():
    # Arrange -- hub gates each URLPattern.callback with login, so the
    # route must stay a flat path() entry (see test_urls.py). GET+POST
    # share one view that dispatches on method (Django has no method
    # routing), keeping the urlconf flat.
    # Act
    match = [p for p in _urls.urlpatterns if str(p.pattern) == "api/preferences/sources"]
    # Assert -- exactly one flat entry pointing at the view.
    assert ([p.callback for p in match]) == [_views.preferences_sources]


_APP = _Path(_views.__file__).parent
_SEARCH_JS = (_APP / "static" / "scholar" / "js" / "search.js").read_text()


def test_sources_grid_is_wired_to_both_persistence_paths():
    # Arrange -- the visitor path is localStorage, the file-user path is
    # the endpoint (user-root JSON). Both are plain client behavior, so
    # the pin is the wiring, same as the retry-button precedent.
    # Act (no Act step: static text inspection)
    # Assert -- grid change persists both ways, load restores either.
    assert (
        "scitex-scholar:sources" in _SEARCH_JS
        and "api/preferences/sources" in _SEARCH_JS
        and "restoreSources" in _SEARCH_JS
    )
