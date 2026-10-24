#!/usr/bin/env python3
"""Saved citation-graph recipes, kept in the shared store.

Thin CUI module: the ``api/graphs/*`` views in ``_django/views.py`` delegate
here; the views stay HTTP adapters (validation + status codes) with no store
logic of their own.

WHERE THE ROWS LIVE
-------------------
:mod:`scitex_dev.store` -- the fleet's shared storage primitive, resolved by
``host_store()`` to this host's PostgreSQL. This module declares a
:class:`~scitex_dev.store.Schema` and calls the primitive directly.

The JSON file (``SAVED_GRAPHS/saved_graphs.json`` under the user root) stays
authoritative for migration: first read-through backfills the store, so a
pre-store library loses nothing. The store has no delete verb -- deletes
HIDE the row, keeping history (store guarantee, README of scitex_dev.store).

``user_root`` is part of the record IDENTITY, not an ambient parameter. One
store serves every user on the host, so two users holding the same graph id
are two distinct rows rather than a silent overwrite.

Fields (additive-only; adding one is a schema edit, never a data migration):

    user_root    TEXT     resolved absolute path of the user root
    graph_id     TEXT     the server-issued id (stable handle)
    name         TEXT     user label (200 chars, hub SavedGraph.name bound)
    seed_doi     TEXT     rebuild seed (500 chars, leaf DOI bound)
    created_by   TEXT     safe username at save time
    created_at   TEXT     ISO-8601 UTC at save time
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Optional

STORE_NAME = "scholar_saved_graphs"
TABLE = "saved_graphs"


def schema():
    """Declare the saved-graphs table. Pure -- opens nothing.

    Built on call rather than at import so that importing the CUI never
    requires the store backend (mirrors storage/_library_index.py).
    """
    from scitex_dev.store import FieldKind, FieldPolicy, FieldRole, MergeRule, Schema

    def ident(kind):
        return FieldPolicy(
            kind=kind,
            role=FieldRole.IDENTITY,
            required=True,
            merge=MergeRule.IMMUTABLE,
            indexed=False,
        )

    def data(kind, *, indexed=False):
        return FieldPolicy(
            kind=kind,
            role=FieldRole.DATA,
            required=False,
            merge=MergeRule.LAST_WRITER_WINS,
            indexed=indexed,
        )

    text = FieldKind.TEXT
    return Schema.build(
        TABLE,
        {
            "user_root": ident(text),
            "graph_id": ident(text),
            "name": data(text),
            "seed_doi": data(text, indexed=True),
            "created_by": data(text),
            "created_at": data(text),
        },
    )


def store_target():
    """Resolve WHERE the rows live. Pure -- does not connect."""
    from scitex_dev.store import host_store

    return host_store(pkg="scitex_scholar", name=STORE_NAME)


class SavedGraphStoreUnavailable(Exception):
    """The saved-graphs store needs privileged provisioning first.

    Provisioning (DDL owner + grants) is an operator/Infra act through the
    authorized migration identity -- the request path never creates shared
    tables itself. Mirrors the SAC turn-ledger shape.
    """


def _open_store():
    """Open the saved-graphs store. Raises naming the target if unreachable."""
    import os

    from scitex_dev.store import (
        Store,
        StoreProvisionError,
        WriterPolicy,
    )

    try:
        return Store(
            store_target(),
            schema(),
            node=socket.gethostname(),
            writer_policy=WriterPolicy.MULTI_WRITER,
            actor="scitex_scholar.saved_graphs",
        )
    except StoreProvisionError as exc:
        role = os.environ.get("PGUSER", "<libpq default>")
        raise SavedGraphStoreUnavailable(
            "the Scholar saved_graphs store requires privileged provisioning "
            f"before PGUSER={role!r} may open it: {exc} Run "
            "provision_store_acl(target, schema) through the authorized "
            "migration identity (scitex_dev.store._provision). Verify with "
            "inspect_store_acl(target, schema)."
        ) from exc


def _root_key(user_root: Path | str) -> str:
    return str(Path(user_root).expanduser().resolve())


def save(user_root, graph_id, name, seed_doi, created_by, created_at) -> None:
    """Insert one saved-graph row (caller validated bounds already)."""
    from scitex_dev.store import NEW_RECORD

    store = _open_store()
    store.put(
        {
            "user_root": _root_key(user_root),
            "graph_id": graph_id,
            "name": name,
            "seed_doi": seed_doi,
            "created_by": created_by,
            "created_at": created_at,
        },
        expected_revision=NEW_RECORD,
    )


def list_for(user_root) -> list[dict[str, Any]]:
    """All visible saved graphs for one user root, oldest first."""
    from scitex_dev.store import Query

    store = _open_store()
    rows = store.read().search(Query.eq("user_root", _root_key(user_root)))
    out = [
        {
            "id": r["graph_id"],
            "name": r["name"],
            "seed_doi": r["seed_doi"],
            "created_by": r["created_by"],
            "created_at": r["created_at"],
        }
        for r in sorted(rows, key=lambda r: r.get("created_at") or "")
        if not r.get("hidden")
    ]
    return out


def rename(user_root, graph_id, name) -> bool:
    """Rename one row; False when the id is unknown for this user."""
    from scitex_dev.store import Query

    store = _open_store()
    key = {"user_root": _root_key(user_root), "graph_id": graph_id}
    rev = store.read().revision(key)
    if rev is None or store.read().is_hidden(key):
        return False
    store.put({**key, "name": name}, expected_revision=rev)
    return True


def hide(user_root, graph_id) -> bool:
    """Hide (store delete verb) one row; False when unknown for this user."""
    store = _open_store()
    key = {"user_root": _root_key(user_root), "graph_id": graph_id}
    rev = store.read().revision(key)
    if rev is None or store.read().is_hidden(key):
        return False
    store.hide(key, expected_revision=rev)
    return True


def backfill_from_file_rows(user_root, file_rows: list[dict[str, Any]]) -> int:
    """One-way migration: file rows missing from the store get inserted.

    Returns the inserted count. Idempotent -- reruns insert nothing.
    """
    try:
        existing = {g["id"] for g in list_for(user_root)}
    except Exception:
        return 0
    n = 0
    for fr in file_rows:
        gid = fr.get("id")
        if not gid or gid in existing:
            continue
        try:
            save(
                user_root,
                gid,
                fr.get("name", ""),
                fr.get("seed_doi", ""),
                fr.get("created_by", "user"),
                fr.get("created_at", ""),
            )
            n += 1
        except Exception:
            continue
    return n


# EOF
