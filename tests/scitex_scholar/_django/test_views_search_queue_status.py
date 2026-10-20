#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U2 (old-direct unification): search engine queue-status chrome.

KEEP: hub progressive_loading panel shape (per-engine status + counts);
search behavior unchanged (the panel reads response metadata only -- no
new endpoint, no streaming, no engine call change). CHANGE: the leaf
`search` view binds the existing pipeline `on_progress(engine, status,
count)` callback and reports last-wins `metadata.engine_events`; the
Search tab renders them in a queue panel that stays hidden until a
search runs. VERIFY: pins with stubbed progress events; panel hidden
by default.
"""

from __future__ import annotations

import json as _json
from pathlib import Path as _Path

from django.test import RequestFactory as _RequestFactory

from scitex_scholar._django import views as _views


def _request(query):
    return _RequestFactory().get("/api/search", {"q": query})


class _ProgressEngine:
    """Stub engine replaying pipeline-style progress events."""

    def __init__(self, events):
        self._events = events

    async def search(
        self,
        query,
        mode=None,
        max_results=20,
        sources=None,
        filters=None,
        on_progress=None,
    ):
        for engine, status, count in self._events:
            if on_progress is not None:
                on_progress(engine, status, count)
        return {
            "results": [],
            "metadata": {"engine_counts": {"pubmed": 0, "arxiv": 0}},
        }


def test_search_collects_engine_progress_events_into_metadata():
    # Arrange
    engine = _ProgressEngine(
        [
            ("pubmed", "loading", 0),
            ("arxiv", "loading", 0),
            ("pubmed", "completed", 3),
            ("arxiv", "error", 0),
        ]
    )
    # Act (distinct query: the view caches per query, so each pin needs
    # its own cache key -- shared state, not shared behavior).
    resp = _views.search(_request("queue-events-collected"), _engine=engine)
    events = _json.loads(resp.content)["metadata"]["engine_events"]
    # Assert -- last-wins per engine, in first-seen order (one compare).
    assert events == [
        {"engine": "pubmed", "status": "completed", "count": 3},
        {"engine": "arxiv", "status": "error", "count": 0},
    ]


def test_search_without_progress_events_reports_empty_event_list():
    # Arrange -- an engine that accepts the callback but never fires it.
    engine = _ProgressEngine([])
    # Act (own cache key, same reason as above).
    resp = _views.search(_request("queue-events-empty"), _engine=engine)
    meta = _json.loads(resp.content)["metadata"]
    # Assert -- the key is always present (deterministic panel shape).
    assert (resp.status_code, meta["engine_events"]) == (200, [])


def test_queue_panel_is_hidden_until_a_search_runs():
    # Arrange
    request = _RequestFactory().get("/")
    # Act
    body = _views.index(request).content.decode()
    # Assert -- the panel exists exactly once, carrying hidden (one compare).
    assert ('<div id="searchQueuePanel" class="search-queue" hidden>' in body) and (
        body.count('id="searchQueuePanel"') == 1
    )


_APP = _Path(_views.__file__).parent
_SEARCH_JS = (_APP / "static" / "scholar" / "js" / "search.js").read_text()


def test_queue_panel_is_wired_to_engine_events():
    # Arrange
    request = _RequestFactory().get("/")
    # Act
    body = _views.index(request).content.decode()
    # Assert -- template container + JS binding to the metadata key.
    assert (
        'id="searchQueueEngines"' in body
        and "searchQueueEngines" in _SEARCH_JS
        and "engine_events" in _SEARCH_JS
    )
