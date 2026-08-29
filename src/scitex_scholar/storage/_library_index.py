#!/usr/bin/env python3
"""Zotero-style index of the scholar library, kept in the shared store.

The index is a DERIVED CACHE of ``MASTER/<paper_id>/metadata.json``. The
filesystem stays authoritative: ``build()`` re-creates every row from it,
so the index can be rebuilt at any time without loss.

WHERE THE ROWS LIVE
-------------------
:mod:`scitex_dev.store` — the fleet's shared storage primitive, resolved by
``host_store()`` to this host's PostgreSQL. This module declares a
:class:`~scitex_dev.store.Schema` and calls the primitive directly; it opens
no path and derives no filesystem location, because a private local file is
a write that reaches nobody.

``library_root`` is part of the record IDENTITY, not an ambient parameter.
One store serves every library on the host, so two roots holding the same
``paper_id`` are two distinct rows rather than a silent overwrite.

Fields (additive-only; adding one is a schema edit, never a data migration):

    library_root   TEXT     resolved absolute path of the library
    paper_id       TEXT     MASTER/<paper_id>
    doi            TEXT
    arxiv_id       TEXT
    pmid           TEXT
    title          TEXT
    year           INTEGER
    venue          TEXT
    is_oa          INTEGER  1 / 0 / None ("unknown")
    authors_json   TEXT     JSON array of author name strings
    abstract       TEXT
    citation_count INTEGER
    updated_at     REAL     metadata.json mtime at index time

Rows for papers that disappear from MASTER are HIDDEN, never deleted: the
store has no delete verb, and a hidden row still carries the history that a
later ``build()`` can un-hide.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any, Iterator, Optional

import scitex_logging as logging

logger = logging.getLogger(__name__)

STORE_NAME = "library_index"
TABLE = "scholar_library_index"

_FIELDS = (
    "library_root",
    "paper_id",
    "doi",
    "arxiv_id",
    "pmid",
    "title",
    "year",
    "venue",
    "is_oa",
    "authors_json",
    "abstract",
    "citation_count",
    "updated_at",
)


def schema():
    """Build this index's :class:`~scitex_dev.store.Schema`.

    Built on call rather than at import so that importing the storage
    package does not drag the store machinery in for callers that never
    touch the index.
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

    def data(kind, *, indexed: bool = False):
        return FieldPolicy(
            kind=kind,
            role=FieldRole.DATA,
            required=False,
            merge=MergeRule.LAST_WRITER_WINS,
            indexed=indexed,
        )

    text = FieldKind.TEXT
    integer = FieldKind.INTEGER
    real = FieldKind.REAL

    return Schema.build(
        TABLE,
        {
            "library_root": ident(text),
            "paper_id": ident(text),
            "doi": data(text, indexed=True),
            "arxiv_id": data(text, indexed=True),
            "pmid": data(text, indexed=True),
            "title": data(text),
            "year": data(integer, indexed=True),
            "venue": data(text),
            "is_oa": data(integer),
            "authors_json": data(text),
            "abstract": data(text),
            "citation_count": data(integer),
            "updated_at": data(real),
        },
    )


def store_target():
    """Resolve WHERE the index lives. Pure — does not connect."""
    from scitex_dev.store import host_store

    return host_store(pkg="scitex_scholar", name=STORE_NAME)


def _open_store():
    """Open the index store. Raises naming the target if it is unreachable."""
    from scitex_dev.store import Store, WriterPolicy

    return Store(
        store_target(),
        schema(),
        node=socket.gethostname(),
        writer_policy=WriterPolicy.MULTI_WRITER,
        actor="scitex_scholar.library_index",
    )


def _root_key(library_root: Path | str) -> str:
    return str(Path(library_root).expanduser().resolve())


# ----- pure derivation (no store, no I/O beyond reading metadata.json) -----


def _is_oa_int(access: dict) -> Optional[int]:
    if "is_open_access" not in access:
        return None
    return 1 if access.get("is_open_access") else 0


def _normalize_id(value: Optional[str]) -> Optional[str]:
    """Treat empty / whitespace-only strings as absent.

    An identifier column distinguishes "no DOI" from a DOI that happens to
    be the empty string; several library entries legitimately have no DOI,
    and letting `""` through makes them look like one paper repeated.
    Applied to arxiv_id and pmid too for consistency.
    """
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _row_from_metadata(
    library_root_key: str, paper_id: str, meta_path: Path
) -> Optional[dict]:
    try:
        md = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    m = md.get("metadata", {}) or {}
    id_ = m.get("id", {}) or {}
    basic = m.get("basic", {}) or {}
    pub = m.get("publication", {}) or {}
    access = m.get("access", {}) or {}
    citation = m.get("citation", {}) or {}
    authors = basic.get("authors")
    authors_json = json.dumps(authors) if isinstance(authors, list) else None
    return {
        "library_root": library_root_key,
        "paper_id": paper_id,
        "doi": _normalize_id(id_.get("doi")),
        "arxiv_id": _normalize_id(id_.get("arxiv_id")),
        "pmid": _normalize_id(id_.get("pmid")),
        "title": basic.get("title"),
        "year": basic.get("year"),
        "venue": pub.get("short_journal") or pub.get("journal"),
        "is_oa": _is_oa_int(access),
        "authors_json": authors_json,
        "abstract": basic.get("abstract"),
        "citation_count": citation.get("count"),
        "updated_at": meta_path.stat().st_mtime,
    }


def collect_rows(library_root: Path | str, verbose: bool = False) -> list[dict]:
    """Derive every index row from MASTER metadata. No store involved.

    Raises ``FileNotFoundError`` when MASTER is missing and ``ValueError``
    when two paper folders claim the same DOI — that is library corruption,
    not a benign duplicate, and it is detected BEFORE anything is written so
    a corrupt library cannot damage the rows already indexed.
    """
    root_key = _root_key(library_root)
    master = Path(root_key) / "MASTER"
    if not master.is_dir():
        raise FileNotFoundError(master)

    rows: list[dict] = []
    doi_to_paper: dict[str, str] = {}
    dupes: dict[str, list[str]] = {}
    for meta_file in master.glob("*/metadata.json"):
        paper_id = meta_file.parent.name
        row = _row_from_metadata(root_key, paper_id, meta_file)
        if row is None:
            if verbose:
                logger.warning(f"Skipped unreadable {meta_file}")
            continue
        rows.append(row)
        doi = row["doi"]
        if doi:
            key = doi.lower()
            if key in doi_to_paper and doi_to_paper[key] != paper_id:
                dupes.setdefault(key, [doi_to_paper[key]]).append(paper_id)
            else:
                doi_to_paper[key] = paper_id

    if dupes:
        lines = [f"  {doi}: {', '.join(pids)}" for doi, pids in sorted(dupes.items())]
        raise ValueError(
            "Duplicate DOIs found in MASTER (library corrupted):\n" + "\n".join(lines)
        )
    return rows


def sort_key(row: dict) -> tuple:
    """Ordering for ``list_all``: newest year first, then title.

    Papers with no year sort LAST rather than as year 0 — an unknown year
    is not an ancient one, and burying them under every dated paper is the
    less misleading of the two.
    """
    year = row.get("year")
    return (year is None, -(year or 0), row.get("title") or "")


# ----- store-backed operations --------------------------------------------


def _rows_for(store, root_key: str) -> Iterator[dict]:
    for row in store.rows():
        values = row.values
        if values.get("library_root") == root_key:
            yield dict(values)


def build(library_root: Path | str, verbose: bool = False) -> int:
    """(Re)build the index from MASTER metadata. Returns row count."""
    from scitex_dev.store import ANY_REVISION

    root_key = _root_key(library_root)
    rows = collect_rows(root_key, verbose=verbose)
    present = {r["paper_id"] for r in rows}

    store = _open_store()
    try:
        stale = [
            r["paper_id"]
            for r in _rows_for(store, root_key)
            if r["paper_id"] not in present
        ]
        with store.batch():
            for row in rows:
                key = {"library_root": root_key, "paper_id": row["paper_id"]}
                if store.is_hidden(key):
                    store.unhide(key, expected_revision=ANY_REVISION)
                store.put(row, expected_revision=ANY_REVISION)
            for paper_id in stale:
                store.hide(
                    {"library_root": root_key, "paper_id": paper_id},
                    expected_revision=ANY_REVISION,
                )
    finally:
        store.close()

    logger.success(f"Indexed {len(rows)} papers for {root_key}")
    return len(rows)


def lookup_by_doi(library_root: Path | str, doi: str) -> Optional[dict]:
    root_key = _root_key(library_root)
    wanted = (doi or "").lower()
    store = _open_store()
    try:
        for row in _rows_for(store, root_key):
            row_doi = row.get("doi")
            if row_doi and row_doi.lower() == wanted:
                return row
    finally:
        store.close()
    return None


def lookup_by_paper_id(library_root: Path | str, paper_id: str) -> Optional[dict]:
    root_key = _root_key(library_root)
    store = _open_store()
    try:
        row = store.get({"library_root": root_key, "paper_id": paper_id})
        return dict(row.values) if row else None
    finally:
        store.close()


def list_all(
    library_root: Path | str, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    root_key = _root_key(library_root)
    store = _open_store()
    try:
        rows = sorted(_rows_for(store, root_key), key=sort_key)
    finally:
        store.close()
    return rows[offset : offset + limit]


# EOF
