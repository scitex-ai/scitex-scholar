"""Saved-graph store CUI: schema declares, file stays authoritative.

One assertion per test (STX-TQ007): tuple compares.
"""

from scitex_scholar.citation_graph import _saved_graph_store as m


def test_store_declares_schema_with_user_root_and_graph_id_identity():
    # Arrange
    schema = m.schema()
    # Act
    identity = sorted(schema.identity_fields)
    # Assert
    assert (schema.name, identity) == (m.TABLE, ["graph_id", "user_root"])


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


class _FakeRead:
    """In-memory stand-in for the scitex_dev.store read handle."""

    def __init__(self, store):
        self._store = store

    def rows(self, include_hidden=False):
        del include_hidden  # the real door filters server-side; list filters
        from types import SimpleNamespace

        return [
            SimpleNamespace(values=dict(entry["data"]))
            for entry in self._store._rows.values()
            if not entry["hidden"]
        ]

    def revision(self, key):
        entry = self._store._rows.get((key["user_root"], key["graph_id"]))
        return None if entry is None else entry["rev"]

    def is_hidden(self, key):
        entry = self._store._rows.get((key["user_root"], key["graph_id"]))
        return False if entry is None else entry["hidden"]


class _FakeStore:
    """In-memory stand-in for the provisioned saved-graphs store."""

    def __init__(self):
        self._rows = {}
        self.puts = []
        self.hides = []

    def put(self, data, expected_revision=None):
        del expected_revision  # revision protocol is the real store's concern
        self.puts.append(dict(data))
        key = (data["user_root"], data["graph_id"])
        if key in self._rows:
            self._rows[key]["data"].update(data)
            self._rows[key]["rev"] += 1
        else:
            self._rows[key] = {"data": dict(data), "rev": 1, "hidden": False}

    def hide(self, key, expected_revision=None):
        del expected_revision
        self.hides.append(dict(key))
        entry = self._rows.get((key["user_root"], key["graph_id"]))
        if entry is not None:
            entry["hidden"] = True

    def read(self):
        return _FakeRead(self)


def _provisioned():
    """Offline store double (PA-306: passed as a parameter, never patched)."""
    fake = _FakeStore()
    return fake, lambda: fake


def test_save_graph_writes_file_and_mirrors_store(tmp_path):
    # Arrange
    fake, opener = _provisioned()
    # Act
    row = m.save_graph(tmp_path, "Graph", "10.1/x", "alice", _opener=opener)
    # Assert
    assert (
        m._read_file_rows(tmp_path),
        [put["graph_id"] for put in fake.puts],
        (row["name"], row["seed_doi"], row["created_by"], bool(row["id"])),
    ) == ([row], [row["id"]], ("Graph", "10.1/x", "alice", True))


def test_delete_graph_removes_file_row_and_hides_store_row(tmp_path):
    # Arrange
    fake, opener = _provisioned()
    row = m.save_graph(tmp_path, "Graph", "10.1/x", _opener=opener)
    # Act
    known = m.delete_graph(tmp_path, row["id"], _opener=opener)
    # Assert
    assert (
        known,
        m._read_file_rows(tmp_path),
        fake.hides,
        m.list_graphs(tmp_path, _opener=opener),
    ) == (
        True,
        [],
        [{"user_root": m._root_key(tmp_path), "graph_id": row["id"]}],
        [],
    )


def test_delete_graph_unknown_id_changes_nothing(tmp_path):
    # Arrange
    fake, opener = _provisioned()
    row = m.save_graph(tmp_path, "Graph", "10.1/x", _opener=opener)
    # Act
    known = m.delete_graph(tmp_path, "nope", _opener=opener)
    # Assert
    assert (known, m._read_file_rows(tmp_path), fake.hides) == (
        False,
        [row],
        [],
    )


def test_rename_graph_updates_file_and_store(tmp_path):
    # Arrange
    _, opener = _provisioned()
    row = m.save_graph(tmp_path, "Old", "10.1/x", _opener=opener)
    # Act
    known = m.rename_graph(tmp_path, row["id"], "New", _opener=opener)
    # Assert
    assert (
        known,
        m._read_file_rows(tmp_path)[0]["name"],
        m.list_graphs(tmp_path, _opener=opener)[0]["name"],
    ) == (True, "New", "New")


def test_rename_graph_unknown_id_returns_false(tmp_path):
    # Arrange
    fake, opener = _provisioned()
    # Act
    known = m.rename_graph(tmp_path, "nope", "New", _opener=opener)
    # Assert
    assert (known, fake.puts, m._read_file_rows(tmp_path)) == (False, [], [])


def test_store_outage_writes_file_and_serves_it(tmp_path):
    # Arrange -- this host's store is unprovisioned for the test PGUSER, so
    # the real opener raises SavedGraphStoreUnavailable: the live outage
    # path, no patching needed.
    # Act
    row = m.save_graph(tmp_path, "Graph", "10.1/x")
    # Assert
    assert (m.list_graphs(tmp_path), row["name"]) == ([row], "Graph")
