"""Save into an SDK-authorized project before its library directory exists."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.test import RequestFactory, override_settings
from scitex_sdk.ui.project_scope import ProjectEntry

from scitex_scholar._django import views


def paper():
    return {
        "metadata": {
            "id": {"doi": "10.1000/acceptance-filing"},
            "basic": {"title": "Acceptance filing fixture", "year": 2026},
        },
        "container": {"library_id": "ACCEPT-1"},
    }


class FileProjectProvider:
    """A configured host catalog backed by actual per-user directories."""

    def list_projects(self, request):
        if not request.user.is_authenticated:
            return []
        root = Path(settings.SCHOLAR_TEST_PROJECTS_ROOT) / request.user.username
        return [
            ProjectEntry(id=f"{request.user.username}/{path.name}", name=path.name)
            for path in sorted(root.iterdir())
            if path.is_dir()
        ]


@pytest.fixture(autouse=True)
def provider(tmp_path):
    root = tmp_path / "host-projects"
    (root / "alice/acceptance-project").mkdir(parents=True)
    (root / "bob/private-project").mkdir(parents=True)
    with override_settings(
        SCITEX_PROJECT_PROVIDER=f"{__name__}.FileProjectProvider",
        SCHOLAR_TEST_PROJECTS_ROOT=root,
    ):
        yield root


def request_for(root, key="alice/acceptance-project", bulk=False, username="alice"):
    payload = {"papers": [paper()]} if bulk else paper()
    if key is not None:
        payload["project"] = key
    request = RequestFactory().post(
        "/api/library/save-bulk" if bulk else "/api/library/save",
        data=json.dumps(payload),
        content_type="application/json",
    )
    request.user = SimpleNamespace(username=username, pk=123, is_authenticated=True)
    request.scholar_library_root = root
    return request


@pytest.mark.parametrize("bulk", [False, True])
def test_new_project_accepts_real_save(tmp_path, bulk):
    # Arrange
    root = tmp_path / "alice-library"
    request = request_for(root, bulk=bulk)

    # Act
    response = (views.library_save_bulk if bulk else views.library_save)(request)
    link = root / "acceptance-project/ACCEPT-1"
    # Assert
    assert (
        response.status_code,
        link.is_symlink(),
        link.resolve() == (root / "MASTER/ACCEPT-1").resolve(),
        (root / "MASTER/ACCEPT-1/metadata.json").is_file(),
    ) == (200, True, True, True), response.content


def test_new_project_lists_nothing_then_only_its_first_save(tmp_path):
    # Arrange -- issue #312: the library already holds a user-scope paper;
    # the newly created project has no folder yet.
    root = tmp_path / "alice-library"
    other = paper()
    other["metadata"]["id"]["doi"] = "10.1000/user-scope"
    other["container"]["library_id"] = "USER-1"
    user_save = RequestFactory().post(
        "/api/library/save", data=json.dumps(other), content_type="application/json"
    )
    user_save.user = SimpleNamespace(username="alice", pk=123, is_authenticated=True)
    user_save.scholar_library_root = root
    views.library_save(user_save)

    def listed():
        request = RequestFactory().get(
            "/api/library", {"project": "alice/acceptance-project"}
        )
        request.scholar_library_root = root
        return [
            p["paper_id"]
            for p in json.loads(views.library_list(request).content)["papers"]
        ]

    # Act
    before = listed()
    saved = views.library_save(request_for(root)).status_code
    after = listed()
    # Assert
    assert (before, saved, after) == ([], 200, ["ACCEPT-1"])


def test_bare_slug_can_identify_the_requesters_own_project(tmp_path):
    # Arrange
    request = request_for(tmp_path, key="acceptance-project")
    # Act
    response = views.library_save(request)
    # Assert
    assert (
        response.status_code,
        (tmp_path / "acceptance-project/ACCEPT-1").is_symlink(),
    ) == (200, True), response.content


def test_inaccessible_project_cannot_create_or_save_any_files(tmp_path):
    # Arrange
    root = tmp_path / "alice-library"

    # Act
    response = views.library_save(request_for(root, key="bob/private-project"))
    # Assert
    assert (response.status_code, root.exists()) == (400, False)


def test_another_user_cannot_provision_a_project_missing_from_their_provider(tmp_path):
    # Arrange
    root = tmp_path / "bob-library"

    # Act
    response = views.library_save(request_for(root, username="bob"))
    # Assert
    assert (response.status_code, root.exists()) == (400, False)


@pytest.mark.parametrize("key", ["../MASTER", "alice/../escape", "MASTER", 123])
def test_unsafe_target_is_refused_before_writing(tmp_path, key):
    # Arrange
    root = tmp_path / "alice-library"

    # Act
    response = views.library_save(request_for(root, key=key))
    # Assert
    assert (response.status_code, root.exists()) == (400, False)


def test_symlinked_project_cannot_redirect_the_save(tmp_path):
    # Arrange
    root = tmp_path / "alice-library"
    outside = tmp_path / "other-user"
    root.mkdir()
    outside.mkdir()
    (root / "acceptance-project").symlink_to(outside, target_is_directory=True)

    # Act
    response = views.library_save(request_for(root))
    # Assert
    assert (
        response.status_code,
        (root / "MASTER").exists(),
        list(outside.iterdir()),
    ) == (400, False, [])


def test_user_scope_save_does_not_create_a_project(tmp_path):
    # Arrange
    request = request_for(tmp_path, key=None)
    # Act
    response = views.library_save(request)
    # Assert
    assert (
        response.status_code,
        (tmp_path / "acceptance-project").exists(),
        (tmp_path / "MASTER/ACCEPT-1/metadata.json").is_file(),
    ) == (200, False, True)


def test_provider_failure_propagates_without_writing(tmp_path):
    # Arrange
    root = tmp_path / "alice-library"
    # Act
    with override_settings(SCHOLAR_TEST_PROJECTS_ROOT=tmp_path / "absent-catalog"):
        try:
            views.library_save(request_for(root))
        except FileNotFoundError:
            failure = True
        else:
            failure = False
    # Assert
    assert (failure, root.exists()) == (True, False)
