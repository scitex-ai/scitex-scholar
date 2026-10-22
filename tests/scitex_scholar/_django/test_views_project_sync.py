"""Slice 3c (CCT4130 slice-3 project-sync UI reflection).

Old-direct parity gap, measured 2026-10-17: hub's Scholar pairs a visible
project picker with project-scoped library behavior -- saves file into the
current project tree (ensure_project_link) and the Library view is
project-aware. The leaf has the slot (SDK app-header project-selector) and
the backend (api/projects over ScholarLocalProjectProvider), but the slot
renders NOTHING (scope=user without allow_user_scope), library_list rows
carry no project membership, and saves ignore any selected project.

This slice reflects project sync into the leaf over EXISTING verbs
(build_project_membership, add_project_to_master, link shape
library/<project>/ -> ../MASTER/<id>): visible header picker, per-row
projects + ?project= filter, save-to-project filing. No new stores.
"""

import json as _json
from pathlib import Path

from django.test import RequestFactory

from scitex_scholar._django import views
from tests.scitex_scholar._django.test_views import _library_env, _seed_library

TEMPLATE = (
    Path(views.__file__).parent
    / "templates"
    / "scholar"
    / "workspace_content.html"
).read_text()
LIBRARY_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "library.js"
).read_text()
SEARCH_JS = (
    Path(views.__file__).parent / "static" / "scholar" / "js" / "search.js"
).read_text()


def test_user_header_keeps_picker_suppressed():
    """User scope never opts into the picker (tested page contract).

    Scholar is user-scoped; the SDK picker renders for project scope only.
    Standalone project selection travels through the Library chips'
    ?project= navigation, which the server resolves and remembers.
    """
    # Arrange
    # Act
    opted = "allow_user_scope" in TEMPLATE
    # Assert
    assert not opted


def test_library_chips_navigate_with_project_query():
    """Chips select via the picker's ?project= contract, no new backend."""
    # Arrange
    # Act
    wired = ("?project=" in LIBRARY_JS, "/api/projects" in LIBRARY_JS)
    # Assert
    assert wired == (True, True)


def test_library_tab_carries_project_chips():
    """The Library tab filters by project; old-direct scopes the view."""
    # Arrange
    # Act
    present = 'id="libraryProjectChips"' in TEMPLATE
    # Assert
    assert present


def test_library_tab_carries_current_project_indicator():
    """The Library tab says which project the view is synced to."""
    # Arrange
    # Act
    present = 'id="libraryProjectCurrent"' in TEMPLATE
    # Assert
    assert present


def test_library_js_reads_project_selection():
    """Library actions follow ?project=, the picker's navigation contract."""
    # Arrange
    # Act
    reads = ("URLSearchParams" in LIBRARY_JS, '"project"' in LIBRARY_JS)
    # Assert
    assert reads == (True, True)


def test_search_js_sends_project_on_save():
    """Search saves file into the selected project, not just the user root."""
    # Arrange
    # Act
    sends = ("project" in SEARCH_JS, "savePayload" in SEARCH_JS)
    # Assert
    assert sends == (True, True)


def test_project_strings_are_translated_labels():
    """Project UI copy is {% trans %} labels, not English literals (JA rule)."""
    # Arrange
    # Act
    labelled = ('{% trans "Project" %}' in TEMPLATE,)
    # Assert
    assert labelled == (True,)


def test_index_context_reports_user_scope_without_project(tmp_path):
    """No selection is explicit user scope, never an implied project."""
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act
        ctx = views.index_context(rf.get("/"))
        # Assert
        assert ctx["current_scope"] == "user"


def test_index_context_reports_project_scope_for_selected_project(tmp_path):
    """?project= through the provider access list resolves and sticks."""
    # Arrange
    with _library_env(tmp_path):
        import os

        root = Path(os.environ["SCITEX_SCHOLAR_LIBRARY_ROOT"])
        (root / "projA").mkdir(parents=True, exist_ok=True)
        rf = RequestFactory()
        # Act
        ctx = views.index_context(rf.get("/?project=projA"))
        # Assert
        assert (ctx["current_project"], ctx["current_scope"]) == ("projA", "project")


def test_library_list_rows_carry_projects(tmp_path):
    """Rows say which projects hold them; unfiled papers carry []."""
    # Arrange
    with _library_env(tmp_path):
        import os

        root = Path(os.environ["SCITEX_SCHOLAR_LIBRARY_ROOT"])
        _seed_library(root)
        rf = RequestFactory()
        # Act
        data = _json.loads(views.library_list(rf.get("/api/library")).content)
        # Assert
        assert data["papers"][0]["projects"] == []


def test_library_list_project_filter_narrows_to_filed(tmp_path):
    """?project= shows only papers filed under that project."""
    # Arrange
    with _library_env(tmp_path):
        from scitex_scholar.storage._project_reconcile import (
            add_project_to_master,
        )

        _seed_library(tmp_path, paper_id="PID1", doi="10.3c/one", title="One")
        _seed_library(tmp_path, paper_id="PID2", doi="10.3c/two", title="Two")
        proj = tmp_path / "projA"
        proj.mkdir()
        (proj / "PID1").symlink_to("../MASTER/PID1")
        add_project_to_master(tmp_path, "PID1", "projA")
        rf = RequestFactory()
        # Act
        data = _json.loads(
            views.library_list(rf.get("/api/library?project=projA")).content
        )
        # Assert
        assert [p["paper_id"] for p in data["papers"]] == ["PID1"]


def test_library_list_rejects_traversal_project(tmp_path):
    """?project= is a path component; traversal fails closed."""
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        # Act
        resp = views.library_list(rf.get("/api/library?project=../MASTER"))
        # Assert
        assert resp.status_code == 400


def test_library_save_files_into_project(tmp_path):
    """Save with project files the symlink and reports the filing."""
    # Arrange
    with _library_env(tmp_path):
        (tmp_path / "projA").mkdir()
        rf = RequestFactory()
        payload = {
            "metadata": {
                "id": {"doi": "10.3c/filed"},
                "basic": {"title": "Filed", "year": 2025},
            },
            "container": {"library_id": "PIDF"},
            "project": "projA",
        }
        # Act
        data = _json.loads(
            views.library_save(
                rf.post(
                    "/api/library/save",
                    data=_json.dumps(payload),
                    content_type="application/json",
                )
            ).content
        )
        filed = (tmp_path / "projA" / "PIDF").is_symlink()
        # Assert
        assert (data["project"], filed) == ("projA", True)


def test_library_save_rejects_unknown_project(tmp_path):
    """Filing into a project that does not exist fails closed, no save."""
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        payload = {
            "metadata": {
                "id": {"doi": "10.3c/noproj"},
                "basic": {"title": "NoProj", "year": 2025},
            },
            "container": {"library_id": "PIDN"},
            "project": "ghost",
        }
        # Act
        resp = views.library_save(
            rf.post(
                "/api/library/save",
                data=_json.dumps(payload),
                content_type="application/json",
            )
        )
        # Assert
        assert (resp.status_code, (tmp_path / "MASTER" / "PIDN").exists()) == (
            400,
            False,
        )


def test_library_save_rejects_traversal_project(tmp_path):
    """A project that escapes the library root fails closed, no save."""
    # Arrange
    with _library_env(tmp_path):
        rf = RequestFactory()
        payload = {
            "metadata": {
                "id": {"doi": "10.3c/traversal"},
                "basic": {"title": "Traversal", "year": 2025},
            },
            "container": {"library_id": "PIDT"},
            "project": "../MASTER",
        }
        # Act
        resp = views.library_save(
            rf.post(
                "/api/library/save",
                data=_json.dumps(payload),
                content_type="application/json",
            )
        )
        # Assert
        assert (resp.status_code, (tmp_path / "MASTER" / "PIDT").exists()) == (
            400,
            False,
        )


def test_library_save_without_project_leaves_unfiled(tmp_path):
    """The default stays user-scoped: saved, filed nowhere, project null."""
    # Arrange
    with _library_env(tmp_path):
        (tmp_path / "projA").mkdir()
        rf = RequestFactory()
        payload = {
            "metadata": {
                "id": {"doi": "10.3c/plain"},
                "basic": {"title": "Plain", "year": 2025},
            },
            "container": {"library_id": "PIDP"},
        }
        # Act
        data = _json.loads(
            views.library_save(
                rf.post(
                    "/api/library/save",
                    data=_json.dumps(payload),
                    content_type="application/json",
                )
            ).content
        )
        # Assert
        assert (data["project"], (tmp_path / "projA" / "PIDP").exists()) == (
            None,
            False,
        )


def test_library_save_bulk_files_each_into_project(tmp_path):
    """Bulk save files every row into the selected project."""
    # Arrange
    with _library_env(tmp_path):
        (tmp_path / "projA").mkdir()
        rf = RequestFactory()
        papers = [
            {
                "metadata": {"id": {"doi": f"10.3c/b{i}"}, "basic": {"title": f"B{i}"}},
                "container": {"library_id": f"PIDB{i}"},
            }
            for i in (1, 2)
        ]
        # Act
        data = _json.loads(
            views.library_save_bulk(
                rf.post(
                    "/api/library/save-bulk",
                    data=_json.dumps({"papers": papers, "project": "projA"}),
                    content_type="application/json",
                )
            ).content
        )
        filed = [(tmp_path / "projA" / f"PIDB{i}").is_symlink() for i in (1, 2)]
        # Assert
        assert (len(data["saved"]), filed) == (2, [True, True])


def test_library_strip_has_no_orphan_separators():
    # Arrange -- operator 2026-10-22 (screenshot loop): lone '|' dividers
    # after Export and after the project indicator read as broken flex.
    # The rows below are flex-wrapped with gap, so separators have no job.
    # Act
    orphan_free = 'class="library-io__sep"' not in TEMPLATE
    # Assert
    assert orphan_free


def test_library_export_select_fits_longest_option():
    # Arrange -- operator 2026-10-22 (screenshot loop): the select clipped
    # 'BibTeX (.bib' with no closing paren (160px cap). The strip rule
    # drops the cap and floors the width at 11em.
    # Act
    css = (
        Path(views.__file__).parent
        / "static" / "scholar" / "css" / "_partials" / "_library.css"
    ).read_text()
    fits = "min-width: 11em" in css and "max-width: 160px" not in css
    # Assert
    assert fits


def test_library_intro_names_the_per_paper_enrich_action():
    # Arrange -- operator 2026-10-22 (screenshot loop): the intro said
    # 'Use Enrich' with no Enrich control in view. Enrich IS per-row
    # (library.js enrich button); the copy must say per-paper.
    # Act
    names_action = "per-paper" in TEMPLATE and "Enrich" in TEMPLATE
    # Assert
    assert names_action
