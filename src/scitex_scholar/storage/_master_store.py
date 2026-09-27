#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Primary file store for user libraries: ``MASTER/<paper_id>/``.

This module is the WRITE side of the package layout. It owns the files —
PDF, BibTeX and package-schema ``metadata.json`` — while
:mod:`scitex_scholar.storage._library_index` owns the derived query index on
the shared store (fleet PostgreSQL). ``add_paper`` writes the files and then
puts the single derived row best-effort; a store outage warns and never fails
the save, and the next ``library db build`` converges the index.

Callers (CLI, web thin layers) pass an explicit ``library_root``. User-home
resolution (``~/.scitex/scholar``) and project tree links are NOT here —
see :mod:`scitex_scholar.config` (PathManager) and
``scitex_scholar.cli._project_tree``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import scitex_logging as logging

logger = logging.getLogger(__name__)


def paper_id_for(identifier: str, id_type: str) -> str:
    """Filesystem-safe ``MASTER/<paper_id>`` for an identifier."""
    safe = "".join(
        c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in identifier
    ).strip("._")[:120]
    if id_type and not safe.lower().startswith(id_type.lower()):
        safe = f"{id_type}-{safe}" if safe else id_type
    return safe or "unknown"


def _skeleton(identifier: str, id_type: str) -> Dict[str, Any]:
    skeleton: Dict[str, Any] = {
        "metadata": {
            "id": {"doi": None, "arxiv_id": None, "pmid": None},
            "basic": {
                "title": None,
                "year": None,
                "authors": [],
                "abstract": None,
            },
            "publication": {},
            "access": {},
            "citation": {},
        }
    }
    key_map = {"doi": "doi", "arxiv": "arxiv_id", "pmid": "pmid"}
    if id_type in key_map:
        skeleton["metadata"]["id"][key_map[id_type]] = identifier
    return skeleton


def _merge_metadata(
    skeleton_meta: Dict[str, Any], metadata: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge caller metadata over the skeleton.

    Explicit nested sections win. Flat search-result keys (title, year,
    authors, abstract, journal, doi, arxiv_id, pmid) fill only gaps — the
    skeleton placeholders are ``None`` (key present), so ``setdefault``
    alone would keep them.
    """
    merged = dict(skeleton_meta)
    flat = dict(metadata or {})
    for section, values in flat.items():
        if isinstance(values, dict):
            merged.setdefault(section, {}).update(values)

    def _fill(section: str, key: str, value: Any) -> None:
        if value is None:
            return
        target = merged.setdefault(section, {})
        if target.get(key) is None:
            target[key] = value

    for key in ("title", "year", "authors", "abstract"):
        _fill("basic", key, flat.get(key))
    _fill("publication", "journal", flat.get("journal"))
    for key in ("doi", "arxiv_id", "pmid"):
        _fill("id", key, flat.get(key))
    for section, values in flat.items():
        if not isinstance(values, dict) and section not in (
            "title",
            "year",
            "authors",
            "abstract",
            "journal",
            "doi",
            "arxiv_id",
            "pmid",
        ):
            merged[section] = values
    return merged


def _index_row_best_effort(library_root: Path, paper_id: str) -> None:
    """Put the single derived index row. Warns, never raises."""
    try:
        from scitex_dev.store import ANY_REVISION

        from ._library_index import _open_store, _root_key, _row_from_metadata

        root_key = _root_key(library_root)
        meta_path = library_root / "MASTER" / paper_id / "metadata.json"
        row = _row_from_metadata(root_key, paper_id, meta_path)
        if row is None:
            return
        store = _open_store()
        try:
            key = {"library_root": root_key, "paper_id": paper_id}
            if store.is_hidden(key):
                store.unhide(key, expected_revision=ANY_REVISION)
            store.put(row, expected_revision=ANY_REVISION)
        finally:
            store.close()
    except Exception as exc:  # store outage must not fail the save
        logger.warning(f"index put skipped for {paper_id}: {exc}")


def add_paper(
    library_root: Path | str,
    identifier: str,
    id_type: str,
    pdf_path: Optional[Path | str] = None,
    bibtex_content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Path]:
    """Add a paper under ``MASTER/<paper_id>/``. Returns rel paths.

    Writes ``<paper_id>.pdf`` (copied), ``<paper_id>.bib`` and
    ``metadata.json`` (package schema), then indexes the row best-effort.
    Idempotent for existing files (PDF copy skipped when present).
    """
    library_root = Path(library_root)
    paper_id = paper_id_for(identifier, id_type)
    paper_dir = library_root / "MASTER" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Path] = {}

    if pdf_path and Path(pdf_path).exists():
        dest_pdf = paper_dir / f"{paper_id}.pdf"
        if not dest_pdf.exists():
            shutil.copy2(pdf_path, dest_pdf)
        result["pdf"] = dest_pdf.relative_to(library_root)

    if bibtex_content:
        dest_bib = paper_dir / f"{paper_id}.bib"
        dest_bib.write_text(bibtex_content)
        result["bibtex"] = dest_bib.relative_to(library_root)

    skeleton = _skeleton(identifier, id_type)
    skeleton["metadata"] = _merge_metadata(skeleton["metadata"], metadata)
    (paper_dir / "metadata.json").write_text(
        json.dumps(skeleton, indent=2, ensure_ascii=False)
    )

    _index_row_best_effort(library_root, paper_id)
    return result


def get_paper_path(
    library_root: Path | str,
    identifier: str,
    id_type: str,
    file_type: str = "pdf",
) -> Optional[Path]:
    """Absolute path to a paper file; None when absent.

    Checks the package ``MASTER/`` store first, then the legacy hub
    ``papers/<id_type>/`` layout.
    """
    library_root = Path(library_root)
    safe_id = paper_id_for(identifier, id_type)
    paper_path = library_root / "MASTER" / safe_id / f"{safe_id}.{file_type}"
    if paper_path.exists():
        return paper_path
    legacy_safe = identifier.replace("/", "_").replace(":", "_")
    legacy_path = (
        library_root / "papers" / id_type / f"{legacy_safe}.{file_type}"
    )
    if legacy_path.exists():
        return legacy_path
    return None


def list_papers(library_root: Path | str) -> List[Dict[str, Any]]:
    """Every paper in the library: package ``MASTER/`` plus legacy rows."""
    library_root = Path(library_root)
    papers: List[Dict[str, Any]] = []
    seen = set()

    master = library_root / "MASTER"
    if master.is_dir():
        for pdf_file in sorted(master.glob("*/*.pdf")):
            paper_id = pdf_file.parent.name
            bib_file = pdf_file.with_name(f"{paper_id}.bib")
            papers.append(
                {
                    "identifier": paper_id,
                    "id_type": "master",
                    "pdf_path": pdf_file,
                    "bib_path": bib_file if bib_file.exists() else None,
                }
            )
            seen.add(pdf_file.resolve())

    for id_type in ["doi", "pmid", "arxiv"]:
        type_dir = library_root / "papers" / id_type
        if not type_dir.exists():
            continue
        for pdf_file in type_dir.glob("*.pdf"):
            if pdf_file.resolve() in seen:
                continue
            identifier = pdf_file.stem
            bib_file = pdf_file.with_suffix(".bib")
            papers.append(
                {
                    "identifier": identifier,
                    "id_type": id_type,
                    "pdf_path": pdf_file,
                    "bib_path": bib_file if bib_file.exists() else None,
                }
            )

    return papers


__all__ = [
    "paper_id_for",
    "add_paper",
    "get_paper_path",
    "list_papers",
]
