#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/_library_db.py

"""``library db`` — the derived index over the scholar library.

Split out of ``_cli/library.py`` in the same change that moved the index off
a private file and onto the shared store (:mod:`scitex_dev.store`), so the
group and the backend it drives read as one thing.

``library.py`` re-exports every command here, because ``_cli_main.py`` and
``_cli/aliases.py`` import them by name to keep the deprecated top-level
``db`` aliases dispatching to a single implementation.
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import click

from ._library_shared import default_library_root
from ._scaffolding import CONTEXT_SETTINGS

__all__ = [
    "library_db",
    "library_db_audit",
    "library_db_build",
    "library_db_list",
    "library_db_lookup",
]


@click.group("db", context_settings=CONTEXT_SETTINGS)
def library_db() -> None:
    """Manage the library index."""


@library_db.command("build")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--verbose", is_flag=True)
@click.option("--dry-run", is_flag=True, help="Print plan without rebuilding.")
@click.option("--yes", "-y", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def library_db_build(library_root, verbose, dry_run, yes, as_json):
    """(Re)build the index from MASTER metadata.

    \b
    Example:
      $ scitex-scholar library db build --verbose
    """
    root = library_root or default_library_root()
    if dry_run:
        click.echo(f"DRY RUN — would (re)build index for {root}")
        return
    from ..storage import _library_index as idx

    n = idx.build(root, verbose=verbose)
    store = str(idx.store_target().locator)
    if as_json:
        click.echo(_json.dumps({"indexed": n, "store": store}))
    else:
        click.echo(f"{n} papers indexed for {root} in {store}")


@library_db.command("lookup")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--doi", default=None)
@click.option("--paper-id", default=None)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def library_db_lookup(library_root, doi, paper_id, as_json):
    """Fetch a paper by DOI or paper_id.

    \b
    Example:
      $ scitex-scholar library db lookup --doi 10.1038/nature12373
    """
    if not doi and not paper_id:
        raise click.UsageError("Provide --doi or --paper-id.")
    if doi and paper_id:
        raise click.UsageError("--doi and --paper-id are mutually exclusive.")

    root = library_root or default_library_root()
    from ..storage import _library_index as idx

    row = (
        idx.lookup_by_doi(root, doi) if doi else idx.lookup_by_paper_id(root, paper_id)
    )
    if row is None:
        raise click.ClickException("Not found")
    click.echo(_json.dumps(row, indent=2, default=str))


@library_db.command("list")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("--offset", type=int, default=0, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def library_db_list(library_root, limit, offset, as_json):
    """List indexed papers.

    \b
    Example:
      $ scitex-scholar library db list --limit 5
    """
    root = library_root or default_library_root()
    from ..storage import _library_index as idx

    rows = idx.list_all(root, limit=limit, offset=offset)
    if as_json:
        click.echo(_json.dumps(list(rows), indent=2, default=str))
        return
    for r in rows:
        click.echo(
            f"{r['paper_id']}\t{r.get('year') or ''}\t{(r.get('title') or '')[:80]}"
        )


@library_db.command("audit")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--json", "as_json", is_flag=True)
@click.option("--strict", is_flag=True, help="Exit 1 when issues found.")
def library_db_audit(library_root, as_json, strict):
    """Report library anomalies (read-only).

    \b
    Example:
      $ scitex-scholar library db audit --json
    """
    root = library_root or default_library_root()
    from ..storage._library_audit import audit, format_report

    report = audit(root)
    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
    else:
        click.echo(format_report(report))
    if strict and report.has_issues:
        sys.exit(1)


# EOF
