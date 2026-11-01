"""Graph persistence against real files and a private PostgreSQL cluster."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

import pytest

from scitex_scholar.citation_graph import _saved_graph_store as graphs


def test_store_declares_schema_with_user_root_and_graph_id_identity():
    # Arrange
    schema = graphs.schema()
    # Act
    identity = sorted(schema.identity_fields)
    # Assert
    assert (schema.name, identity) == (graphs.TABLE, ["graph_id", "user_root"])


def test_hook_rules_declare_five_scholar_scope_rules():
    # Arrange
    from scitex_scholar._hook_rules import provide

    # Act
    ids = sorted(r.id for r in provide())
    # Assert
    assert ids == [
        "scholar.bulk-verbs-explicit-rows-only",
        "scholar.file-authoritative-store-derived",
        "scholar.per-user-root-scope",
        "scholar.search-fails-closed",
        "scholar.thin-view-cui-owns-logic",
    ]


def test_hooks_entry_point_registered_in_pyproject():
    # Arrange
    from pathlib import Path

    # Act
    pyproject = (Path(__file__).parents[3] / "pyproject.toml").read_text()
    # Assert
    assert (
        '[project.entry-points."scitex_dev.hooks"]' in pyproject,
        "scitex_scholar._hook_rules:provide" in pyproject,
    ) == (True, True)


@pytest.fixture(scope="module")
def graph_cluster():
    """Own a throwaway server; never use the fleet's production/shared store."""
    from scitex_dev.store.testing import ephemeral_cluster_dsn

    with ephemeral_cluster_dsn() as dsn:
        yield dsn


@pytest.fixture
def graph_store(graph_cluster):
    from scitex_dev.store import Store, StoreTarget, WriterPolicy
    from scitex_dev.store.testing import ephemeral_schema

    with ephemeral_schema(graph_cluster, prefix="scholar_graph") as dsn:
        store = Store(
            StoreTarget.postgres(dsn, pkg="scholar", name=graphs.STORE_NAME),
            graphs.schema(),
            node="test",
            writer_policy=WriterPolicy.MULTI_WRITER,
        )
        try:
            yield store, dsn
        finally:
            store.close()


def test_file_authority_survives_a_stale_readable_readonly_mirror(
    tmp_path, graph_store
):
    # Arrange -- import a genuine legacy DB-only graph, then make that mirror read-only.
    store, _ = graph_store
    opener = lambda: store
    graphs.save(tmp_path, "legacy", "Old", "10.1/old", "owner", "now", _opener=opener)
    imported = graphs.list_graphs(tmp_path, _opener=opener)
    store._connection.execute("SET default_transaction_read_only=on")
    # Act -- all lifecycle changes must remain visible despite rejected mirror writes.
    graphs.rename_graph(tmp_path, "legacy", "Renamed", _opener=opener)
    renamed = graphs.list_graphs(tmp_path, _opener=opener)
    added = graphs.save_graph(tmp_path, "New", "10.1/new", _opener=opener)
    graphs.delete_graph(tmp_path, "legacy", _opener=opener)
    visible = graphs.list_graphs(tmp_path, _opener=opener)
    mirror = graphs.list_for(tmp_path, _opener=opener)
    # Assert
    assert (imported[0]["id"], renamed[0]["name"], visible, mirror[0]["name"]) == (
        "legacy",
        "Renamed",
        [added],
        "Old",
    )


def test_an_existing_empty_file_never_resurrects_legacy_mirror_rows(
    tmp_path, graph_store
):
    # Arrange
    store, _ = graph_store
    graphs.save(
        tmp_path, "old", "Old", "10.1/old", "owner", "now", _opener=lambda: store
    )
    graphs._write_file_rows(tmp_path, [])
    # Act
    result = graphs.list_graphs(tmp_path, _opener=lambda: store)
    # Assert
    assert result == []


def test_multi_seed_recipe_and_user_isolation_roundtrip(tmp_path, graph_store):
    # Arrange
    store, _ = graph_store
    owner = tmp_path / "owner"
    other = tmp_path / "other"
    # Act
    row = graphs.save_graph(
        owner,
        "Pair",
        "10.1/a",
        seed_dois=["10.1/a", "10.1/b"],
        top_n=7,
        _opener=lambda: store,
    )
    result = graphs.list_graphs(owner, _opener=lambda: store)
    # Assert
    assert (result, graphs.list_graphs(other, _opener=lambda: store)) == ([row], [])


def test_failed_atomic_serialization_preserves_previous_library(tmp_path):
    # Arrange
    rows = [{"id": "original", "name": "Keep"}]
    graphs._write_file_rows(tmp_path, rows)
    # Act
    failed = False
    try:
        graphs._write_file_rows(tmp_path, [{"bad": {object()}}])
    except TypeError:
        failed = True
    # Assert
    assert (
        failed,
        graphs._read_file_rows(tmp_path),
        list(graphs._file_path(tmp_path).parent.glob(".saved-graphs-*")),
    ) == (True, rows, [])


def test_corrupt_library_is_never_silently_replaced(tmp_path):
    # Arrange
    path = graphs._file_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    # Act
    failed = False
    try:
        graphs.save_graph(tmp_path, "New", "10.1/new")
    except graphs.SavedGraphFileError:
        failed = True
    # Assert
    assert (failed, path.read_text()) == (True, "{broken")


def _append_graph(args):
    from scitex_dev.store import Store, StoreTarget, WriterPolicy

    root, dsn, index = args
    store = Store(
        StoreTarget.postgres(dsn, pkg="scholar", name=graphs.STORE_NAME),
        graphs.schema(),
        node=str(index),
        writer_policy=WriterPolicy.MULTI_WRITER,
    )
    try:
        return graphs.save_graph(
            root, str(index), f"10.1/{index}", _opener=lambda: store
        )["id"]
    finally:
        store.close()


def test_concurrent_processes_do_not_lose_saved_graphs(tmp_path, graph_store):
    # Arrange
    _, dsn = graph_store
    graphs._write_file_rows(tmp_path, [])
    # Act
    with ProcessPoolExecutor(max_workers=4) as pool:
        ids = list(
            pool.map(_append_graph, [(str(tmp_path), dsn, i) for i in range(12)])
        )
    rows = json.loads(graphs._file_path(tmp_path).read_text())
    # Assert
    assert {row["id"] for row in rows} == set(ids)


@pytest.fixture
def graph_http():
    """Real Django HTTP adapters with no project model or external network service."""
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            SECRET_KEY="graph-tests-only", DEFAULT_CHARSET="utf-8", INSTALLED_APPS=[]
        )
    from scitex_scholar._django import views
    from django.test import RequestFactory

    return views, RequestFactory()


def test_http_multi_seed_graph_lifecycle_is_user_scoped(
    tmp_path, graph_store, graph_http
):
    # Arrange
    views, factory = graph_http
    store, _ = graph_store
    owner = tmp_path / "owner"
    other = tmp_path / "other"
    request = factory.post(
        "/api/graphs/save",
        data=json.dumps(
            {"name": "Pair", "seed_dois": ["10.1/a", "10.1/b"], "top_n": 9}
        ),
        content_type="application/json",
    )
    request.scholar_library_root = owner
    # Act
    saved = views.graphs_save(request, _opener=lambda: store)
    graph_id = json.loads(saved.content)["id"]
    rename = factory.post(
        "/api/graphs/rename",
        data=json.dumps({"id": graph_id, "name": "Renamed"}),
        content_type="application/json",
    )
    rename.scholar_library_root = other
    denied = views.graphs_rename(rename, _opener=lambda: store)
    listing = factory.get("/api/graphs/list")
    listing.scholar_library_root = owner
    row = json.loads(views.graphs_list(listing, _opener=lambda: store).content)[
        "graphs"
    ][0]
    delete = factory.post(
        "/api/graphs/delete",
        data=json.dumps({"id": graph_id}),
        content_type="application/json",
    )
    delete.scholar_library_root = owner
    removed = views.graphs_delete(delete, _opener=lambda: store)
    # Assert
    assert (
        saved.status_code,
        row["name"],
        row["seed_dois"],
        row["top_n"],
        denied.status_code,
        removed.status_code,
        graphs._read_file_rows(owner),
    ) == (200, "Pair", ["10.1/a", "10.1/b"], 9, 404, 200, [])


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"name": 12, "seed_doi": "10.1/a"},
        {"name": "x", "seed_dois": "bad"},
        {"name": "x", "seed_dois": [1]},
        {"name": "x", "seed_doi": "10.1/a", "top_n": True},
    ],
)
def test_invalid_graph_bodies_return_400_without_touching_storage(
    tmp_path, graph_http, payload
):
    # Arrange
    views, factory = graph_http
    request = factory.post(
        "/api/graphs/save", data=json.dumps(payload), content_type="application/json"
    )
    request.scholar_library_root = tmp_path
    # Act
    result = views.graphs_save(request)
    # Assert
    assert (result.status_code, graphs._file_path(tmp_path).exists()) == (400, False)


def test_user_home_capability_places_graphs_in_the_user_home(tmp_path, graph_http):
    # Arrange
    from types import SimpleNamespace
    from django.test import override_settings

    views, factory = graph_http
    request = factory.get("/api/graphs/list?project=someone/else")
    request.user = SimpleNamespace(
        username="owner", is_authenticated=True, is_anonymous=False
    )

    def home_provider(req):
        return tmp_path / req.user.username

    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=home_provider):
        root = views._library_root_for(request)
    # Assert
    assert root == tmp_path / "owner/.scitex/scholar/library"


def test_graph_file_cannot_escape_the_user_library_through_a_symlink(tmp_path):
    # Arrange
    root, outside = tmp_path / "owner", tmp_path / "other"
    root.mkdir()
    outside.mkdir()
    protected = outside / "saved_graphs.json"
    protected.write_text("[]")
    (root / "SAVED_GRAPHS").symlink_to(outside, target_is_directory=True)
    # Act
    failed = False
    try:
        graphs.save_graph(root, "Forbidden", "10.1/x")
    except graphs.SavedGraphFileError:
        failed = True
    # Assert
    assert (failed, protected.read_text()) == (True, "[]")
