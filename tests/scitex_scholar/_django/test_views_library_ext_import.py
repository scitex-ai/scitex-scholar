"""Slice 3b (CCT4130 slice-3 Zotero/Connected-Papers reflection).

Old-direct parity gap, measured 2026-10-17: hub's library panel pairs the
BibTeX/RIS import-export with (a) a Zotero section (status LED, import by
all/collection/tags, export-as-BibTeX) and (b) a Connected Papers section
(status LED, import-by-seed-paper-ID). The leaf Library tab has BibTeX
import + export only; neither integration is surfaced.

This slice reflects both into the leaf over the EXISTING package backends
(ZoteroLocalReader, from_connected_papers) and the leaf's own file-based
library store -- thin views, same as library_import/library_export. Remote
API-backed Zotero (ZoteroImporter) is out of scope: the leaf has no account
model, so only the local-DB reader is reflected.
"""

import json as _json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views
from scitex_scholar.core.Paper import Paper
from tests.scitex_scholar._django.test_views import _library_env, _seed_library

TEMPLATE = (
    Path(views.__file__).parent
    / "templates"
    / "scholar"
    / "workspace_content.html"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent
    / "static"
    / "scholar"
    / "js"
    / "library.js"
).read_text()


def _paper(doi, title="Ext Paper", year=2023):
    return Paper.from_dict(
        {
            "metadata": {
                "id": {"doi": doi},
                "basic": {"title": title, "year": year},
            },
            "container": {},
        }
    )


class _FakeReader:
    """Offline ZoteroLocalReader stand-in (PA-306: injected, not patched)."""

    def __init__(self, papers):
        self._papers = papers

    def read_all(self, limit=None):
        return list(self._papers)

    def read_by_collection(self, name):
        return list(self._papers)

    def read_by_tags(self, tags, match_all=False):
        return list(self._papers)

    def list_collections(self):
        return ["Neuroscience", "Methods"]


class _MissingDB:
    """Stand-in for a host with no local Zotero database."""

    def __init__(self):
        raise FileNotFoundError("no zotero.sqlite here")


def _two_papers():
    return [
        _paper("10.9/zotero-one", "Zotero One"),
        _paper("10.9/zotero-two", "Zotero Two"),
    ]


def _post_zotero_import(payload, papers):
    req = RequestFactory().post(
        "/api/library/zotero/import",
        data=_json.dumps(payload),
        content_type="application/json",
    )
    return views.zotero_import(req, _reader=_FakeReader(papers))


# --- routes ---------------------------------------------------------------

def test_ext_import_routes_are_registered():
    # Arrange
    from django.urls import resolve
    # Act
    names = [
        resolve("/api/library/zotero/status").func.__name__,
        resolve("/api/library/zotero/collections").func.__name__,
        resolve("/api/library/zotero/import").func.__name__,
        resolve("/api/library/connected-papers/status").func.__name__,
        resolve("/api/library/connected-papers/import").func.__name__,
    ]
    # Assert
    assert names == [
        "zotero_status",
        "zotero_collections",
        "zotero_import",
        "connected_papers_status",
        "connected_papers_import",
    ]


# --- Zotero status ---------------------------------------------------------

def test_zotero_status_reports_available():
    # Arrange
    rf = RequestFactory()
    # Act
    body = _json.loads(
        views.zotero_status(
            rf.get("/api/library/zotero/status"),
            _reader=_FakeReader([]),
        ).content
    )
    # Assert
    assert body == {"available": True}


def test_zotero_status_reports_unavailable_without_db_paths():
    """Missing DB is available:false -- the FileNotFoundError text names
    server-side search paths, so it must never reach the client."""
    # Arrange
    rf = RequestFactory()
    # Act
    resp = views.zotero_status(rf.get("/api/library/zotero/status"), _reader=_MissingDB)
    body = _json.loads(resp.content)
    # Assert
    assert body == {"available": False}


# --- Zotero import ----------------------------------------------------------

def test_zotero_import_persists_papers_to_leaf_library(tmp_path):
    # Arrange
    rf = RequestFactory()
    # Act -- import, then list the library.
    with _library_env(tmp_path):
        imported = _json.loads(
            _post_zotero_import({"mode": "all"}, _two_papers()).content
        )
        listed = _json.loads(views.library_list(rf.get("/api/library")).content)
        titles = [p.get("title") for p in listed["papers"]]
    # Assert
    result = (
        imported["ok"] is True,
        (imported["imported"], imported["skipped"], imported["total"]),
        "Zotero One" in titles and "Zotero Two" in titles,
    )
    assert result == (True, (2, 0, 2), True)


def test_zotero_import_rejects_unknown_mode():
    # Arrange
    req = RequestFactory().post(
        "/api/library/zotero/import",
        data=_json.dumps({"mode": "favorites"}),
        content_type="application/json",
    )
    # Act
    resp = views.zotero_import(req, _reader=_FakeReader([]))
    # Assert -- fixed message, the raw mode is untrusted input.
    result = (
        resp.status_code,
        _json.loads(resp.content),
    )
    assert result == (
        400,
        {"error": "Unsupported import mode", "supported": ["all", "collection", "tags"]},
    )


def test_zotero_import_skips_already_present_papers(tmp_path):
    """Re-import must not clobber an existing (possibly enriched) record."""
    # Arrange
    rf = RequestFactory()
    with _library_env(tmp_path):
        _seed_library(tmp_path, paper_id="KEEPME1", doi="10.9/zotero-one",
                      title="Enriched Title", year=2023)
        # Act
        imported = _json.loads(
            _post_zotero_import({"mode": "all"}, _two_papers()).content
        )
        listed = _json.loads(views.library_list(rf.get("/api/library")).content)
        by_doi = {p.get("doi"): p.get("title") for p in listed["papers"]}
    # Assert -- one new, one skipped, existing title untouched.
    result = (
        (imported["imported"], imported["skipped"]),
        by_doi["10.9/zotero-one"],
    )
    assert result == ((1, 1), "Enriched Title")


def test_zotero_import_caps_batch_size():
    # Arrange
    big = [_paper(f"10.9/bulk-{i}", f"Bulk {i}") for i in range(501)]
    req = RequestFactory().post(
        "/api/library/zotero/import",
        data=_json.dumps({"mode": "all"}),
        content_type="application/json",
    )
    # Act
    resp = views.zotero_import(req, _reader=_FakeReader(big))
    # Assert -- same 500 cap class as library_import/save-bulk.
    assert resp.status_code == 400


# --- Connected Papers -------------------------------------------------------

def test_connected_papers_status_reports_availability():
    # Arrange
    rf = RequestFactory()
    # Act -- seam True/False: the real probe is an import check (hub parity).
    on = _json.loads(
        views.connected_papers_status(
            rf.get("/api/library/connected-papers/status"), _probe=True
        ).content
    )
    off = _json.loads(
        views.connected_papers_status(
            rf.get("/api/library/connected-papers/status"), _probe=False
        ).content
    )
    # Assert
    assert on == {"available": True} and off == {"available": False}


def test_connected_papers_import_persists_papers(tmp_path):
    # Arrange
    seen = {}

    def _fake_cp(paper_id, **kwargs):
        seen.update(kwargs)
        return {
            "success": True,
            "papers": [_paper("10.9/cp-one", "CP One")],
            "stats": {"node_count": 1, "edge_count": 0},
            "warnings": [],
        }

    rf = RequestFactory()
    req = rf.post(
        "/api/library/connected-papers/import",
        data=_json.dumps({"paper_id": "a" * 40}),
        content_type="application/json",
    )
    # Act
    with _library_env(tmp_path):
        body = _json.loads(
            views.connected_papers_import(req, _importer=_fake_cp).content
        )
        listed = _json.loads(views.library_list(rf.get("/api/library")).content)
    # Assert
    result = (
        body["ok"] is True and body["imported"] == 1,
        [p.get("title") for p in listed["papers"]],
        seen.get("output_format"),
    )
    assert result == (True, ["CP One"], "papers")


def test_connected_papers_import_rejects_blank_and_oversized_ids():
    # Arrange
    rf = RequestFactory()

    def _blank():
        return rf.post(
            "/api/library/connected-papers/import",
            data=_json.dumps({"paper_id": "  "}),
            content_type="application/json",
        )

    def _huge():
        return rf.post(
            "/api/library/connected-papers/import",
            data=_json.dumps({"paper_id": "x" * 200_000}),
            content_type="application/json",
        )

    # Act
    blank = views.connected_papers_import(_blank(), _importer=None)
    huge = views.connected_papers_import(_huge(), _importer=None)
    # Assert -- fixed messages, the raw id is untrusted input (echo class).
    result = (
        blank.status_code,
        huge.status_code,
        "paper_id" not in _json.loads(huge.content).get("error", "paper_id"),
    )
    assert result[0] == 400 and result[1] in (400, 413) and result[2] is True


def test_connected_papers_import_upstream_failure_is_fixed_message():
    # Arrange
    def _failing(paper_id, **kwargs):
        return {"success": False, "error": "upstream exploded: /srv/secret"}

    req = RequestFactory().post(
        "/api/library/connected-papers/import",
        data=_json.dumps({"paper_id": "a" * 40}),
        content_type="application/json",
    )
    # Act
    resp = views.connected_papers_import(req, _importer=_failing)
    body = _json.loads(resp.content)
    # Assert -- server/network internals never reach the client.
    result = (resp.status_code, body)
    assert result == (500, {"error": "Import failed. Try again later."})


# --- template + JS reflection -------------------------------------------------

def test_library_tab_carries_zotero_and_connected_papers_panels():
    # Arrange
    # Act
    panel = (
        '{% trans "Zotero" %}' in TEMPLATE,
        '{% trans "Connected Papers" %}' in TEMPLATE,
        'id="zoteroImportBtn"' in TEMPLATE,
        'id="cpImportBtn"' in TEMPLATE,
    )
    # Assert
    assert panel == (True,) * 4


def test_library_js_wires_ext_import_endpoints():
    # Arrange
    # Act
    wired = (
        "api/library/zotero/status" in LIBRARY_JS,
        "api/library/zotero/import" in LIBRARY_JS,
        "api/library/connected-papers/import" in LIBRARY_JS,
    )
    # Assert
    assert wired == (True,) * 3


def test_slice3b_js_strings_are_translatable():
    # Arrange
    keys = views._js_i18n_dict()
    # Act
    present = (
        "Importing…" in keys,
        "Zotero database not found" in keys,
        "Connected Papers unavailable" in keys,
        "Imported %(imported)s of %(total)s papers" in keys,
        "Enter a Semantic Scholar paper ID" in keys,
    )
    # Assert
    assert present == (True,) * 5
