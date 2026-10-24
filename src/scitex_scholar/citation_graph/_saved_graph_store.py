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

import scitex_logging as _slog
import socket
from pathlib import Path
from typing import Any, Optional

logger = _slog.getLogger(__name__)

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


def save(
    user_root, graph_id, name, seed_doi, created_by, created_at, _opener=None
) -> None:
    """Insert one saved-graph row (caller validated bounds already)."""
    from scitex_dev.store import NEW_RECORD

    store = (_opener or _open_store)()
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


def list_for(user_root, _opener=None) -> list[dict[str, Any]]:
    """All visible saved graphs for one user root, oldest first."""
    store = (_opener or _open_store)()
    key = _root_key(user_root)
    out = []
    for row in store.read().rows():
        values = row.values
        if values.get("user_root") != key:
            continue
        out.append(
            {
                "id": values["graph_id"],
                "name": values["name"],
                "seed_doi": values["seed_doi"],
                "created_by": values["created_by"],
                "created_at": values["created_at"],
            }
        )
    return sorted(out, key=lambda r: r.get("created_at") or "")


def rename(user_root, graph_id, name, _opener=None) -> bool:
    """Rename one row; False when the id is unknown for this user."""
    store = (_opener or _open_store)()
    key = {"user_root": _root_key(user_root), "graph_id": graph_id}
    rev = store.read().revision(key)
    if rev is None or store.read().is_hidden(key):
        return False
    store.put({**key, "name": name}, expected_revision=rev)
    return True


def hide(user_root, graph_id, _opener=None) -> bool:
    """Hide (store delete verb) one row; False when unknown for this user."""
    store = (_opener or _open_store)()
    key = {"user_root": _root_key(user_root), "graph_id": graph_id}
    rev = store.read().revision(key)
    if rev is None or store.read().is_hidden(key):
        return False
    store.hide(key, expected_revision=rev)
    return True


def backfill_from_file_rows(
    user_root, file_rows: list[dict[str, Any]], _opener=None
) -> int:
    """One-way migration: file rows missing from the store get inserted.

    Returns the inserted count. Idempotent -- reruns insert nothing.
    """
    try:
        existing = {g["id"] for g in list_for(user_root, _opener=_opener)}
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
                _opener=_opener,
            )
            n += 1
        except Exception:
            continue
    return n


# ---------------------------------------------------------------------------
# CUI-owned CRUD: graphs as package data (operator 2026-10-24).
#
# The per-user file stays authoritative; the shared store is the derived
# mirror. Every mutation lands in the file first, then mirrors best-effort
# (save -> put, delete -> hide, rename -> put). A store outage never fails
# the call -- the file is the live path and backfill converges the mirror
# on the next provisioned read. The _django layer only validates HTTP and
# forwards; it never touches the file or the store directly.
# ---------------------------------------------------------------------------


def _file_path(user_root: Path | str) -> Path:
    """Single JSON file holding this user's saved graphs."""
    return Path(user_root).expanduser().resolve() / "SAVED_GRAPHS" / "saved_graphs.json"


def _read_file_rows(user_root: Path | str) -> list:
    import json as _json

    path = _file_path(user_root)
    if not path.is_file():
        return []
    try:
        data = _json.loads(path.read_text())
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _write_file_rows(user_root: Path | str, rows: list) -> None:
    import json as _json

    path = _file_path(user_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(rows))


def list_graphs(user_root: Path | str, _opener=None) -> list:
    """All visible saved graphs for one user root, oldest first.

    File-authoritative with store backfill; a store outage serves the file.
    The _opener seam (a zero-arg store factory, like the views' _builder
    seam) is the PA-306-sanctioned injection point for the offline fake.
    """
    file_rows = _read_file_rows(user_root)
    try:
        if file_rows:
            backfill_from_file_rows(user_root, file_rows, _opener=_opener)
        return list_for(user_root, _opener=_opener)
    except SavedGraphStoreUnavailable:
        return file_rows
    except Exception:
        logger.exception("saved-graphs store read failed; serving file")
        return file_rows


def save_graph(
    user_root: Path | str,
    name: str,
    seed_doi: str,
    created_by: str = "user",
    _opener=None,
) -> dict:
    """Insert one saved-graph recipe (caller validated bounds already).

    Returns the stored row (server-issued id + created_at). The store
    mirror is best-effort; only file errors propagate.
    """
    import datetime as _dt
    import uuid as _uuid

    row = {
        "id": _uuid.uuid4().hex,
        "name": name,
        "seed_doi": seed_doi,
        "created_by": created_by,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    rows = _read_file_rows(user_root)
    rows.append(row)
    _write_file_rows(user_root, rows)
    try:
        save(
            user_root,
            row["id"],
            name,
            seed_doi,
            created_by,
            row["created_at"],
            _opener=_opener,
        )
    except SavedGraphStoreUnavailable:
        logger.debug("saved-graphs store unprovisioned; file kept")
    except Exception:
        logger.exception("saved-graphs store mirror failed; file kept")
    return row


def delete_graph(user_root: Path | str, graph_id: str, _opener=None) -> bool:
    """Delete one saved graph; False when the id is unknown for this user.

    File first, then the store mirror is hidden (the store has no delete
    verb). Best-effort on the mirror; only file errors propagate.
    """
    rows = _read_file_rows(user_root)
    kept = [r for r in rows if r.get("id") != graph_id]
    if len(kept) == len(rows):
        return False
    _write_file_rows(user_root, kept)
    try:
        hide(user_root, graph_id, _opener=_opener)
    except SavedGraphStoreUnavailable:
        logger.debug("saved-graphs store unprovisioned; file kept")
    except Exception:
        logger.exception("saved-graphs store hide failed; file kept")
    return True


def rename_graph(
    user_root: Path | str, graph_id: str, name: str, _opener=None
) -> bool:
    """Rename one saved graph; False when the id is unknown for this user.

    File first, then the store mirror. Best-effort on the mirror; only
    file errors propagate.
    """
    rows = _read_file_rows(user_root)
    for row in rows:
        if row.get("id") == graph_id:
            row["name"] = name
            break
    else:
        return False
    _write_file_rows(user_root, rows)
    try:
        rename(user_root, graph_id, name, _opener=_opener)
    except SavedGraphStoreUnavailable:
        logger.debug("saved-graphs store unprovisioned; file kept")
    except Exception:
        logger.exception("saved-graphs store rename failed; file kept")
    return True


# EOF
