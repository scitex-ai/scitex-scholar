"""New generic-host context-call controls using genuine private fixtures."""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings
from django.utils.module_loading import import_string

from scitex_scholar._django import context_builder, views

pytest_plugins = (
    "tests.scitex_scholar._django.test_views_shell_context",
)


@pytest.fixture(
    params=[
        (None, "Beta", "Beta", "Beta"),
        ("foreign", "Beta", "Beta", "Beta"),
        (None, None, "Alpha", "Alpha"),
        ("foreign", None, "Alpha", "Alpha"),
        (None, "Missing", None, "Alpha"),
        ("foreign", "Missing", None, "Alpha"),
    ],
    ids=[
        "none-explicit-valid",
        "foreign-explicit-valid",
        "none-remembered",
        "foreign-remembered",
        "none-explicit-inaccessible",
        "foreign-explicit-inaccessible",
    ],
)
def _generic_host_context_outcomes(request, _private_context):
    host_choice, query, expected_project, remembered = request.param
    project_root = _private_context["paths"]["SCITEX_SCHOLAR_PROJECTS_DIR"]
    (project_root / "Beta").mkdir()
    provider = views.ScholarLocalProjectProvider(project_root)
    foreign_root = _private_context["temp_root"] / "foreign-projects"
    (foreign_root / "Foreign").mkdir(parents=True)
    foreign_provider = views.ScholarLocalProjectProvider(foreign_root)
    host_projects = {
        None: None,
        "foreign": foreign_provider.list_projects()[0],
    }
    builder = import_string(context_builder)
    actual_contexts = []
    expected_contexts = []
    actual_roots = []
    expected_roots = []
    for username in ("alice", "bob"):
        http_request = RequestFactory().get(
            "/apps/scholar/v2/", {"project": query} if query else {}
        )
        http_request.user = get_user_model()(username=username)
        root = _private_context["paths"]["SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE"]
        root = root / username
        if username == "alice":
            root = _private_context["temp_root"] / "bound-library" / username
            http_request.scholar_library_root = root
        provider.remember(http_request, "Alpha")
        with override_settings(SCITEX_APP_MODE="hub"):
            legacy_context = builder(http_request)
            provider.remember(http_request, "Alpha")
            context = builder(http_request, host_projects[host_choice])
        actual_contexts.append(
            (context, provider.last_visited(http_request))
        )
        expected_contexts.append(
            ({**legacy_context, "current_project": expected_project}, remembered)
        )
        actual_roots.append(views._library_root_for(http_request))
        expected_roots.append(root.resolve())
    return {
        "actual_contexts": actual_contexts,
        "expected_contexts": expected_contexts,
        "actual_roots": actual_roots,
        "expected_roots": expected_roots,
    }


def test_generic_host_context_keeps_request_project_authority(
    _generic_host_context_outcomes,
):
    # Arrange
    result = _generic_host_context_outcomes
    # Act
    actual = result["actual_contexts"]
    # Assert
    assert actual == result["expected_contexts"]


def test_generic_host_context_keeps_private_request_roots(
    _generic_host_context_outcomes,
):
    # Arrange
    result = _generic_host_context_outcomes
    # Act
    roots = result["actual_roots"]
    # Assert
    assert roots == result["expected_roots"]
