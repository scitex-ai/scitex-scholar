#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/library.py

"""``library`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so new subcommands — starting with ``library dedupe`` — can be
added without touching that oversized module. See ``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.library import library`` +
``cli.add_command(library)``. The private option-decorators / ``_do_*``
helpers and the ``library_db_*`` commands are re-imported there so the legacy
top-level deprecation aliases keep dispatching to a single implementation.
"""

from __future__ import annotations

import json as _json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS, _CategorizedGroup

# ---------------------------------------------------------------------------
# Group: library
# ---------------------------------------------------------------------------


class _LibraryGroup(_CategorizedGroup):
    SECTIONS = [
        ("Daily", ["list", "open-urls", "refresh"]),
        ("Layout", ["bind", "link-project-tree", "materialize", "dematerialize"]),
        ("Share", ["sync", "export", "zotero"]),
        ("Database", ["db", "audit-files", "dedupe"]),
    ]

    def get_command(self, ctx, name):
        # Real subcommands win.
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd

        # Fall through: if `name` is an existing project under the home
        # library, treat `library <name> <project-root>` as a shorthand
        # for `library bind <name> <project-root>`.
        try:
            home_root = _default_library_root()
            home_proj = home_root / name
        except Exception:
            return None
        if not (home_proj.exists() or home_proj.is_symlink()):
            return None
        return _make_shorthand_bind(name)


def _make_shorthand_bind(project_name: str):
    """Build an ad-hoc Click command for `library <project> <project-root>`.

    Just delegates to the canonical `library_bind` so behavior, flags, and
    error handling stay in one place.
    """

    @click.command(
        name=project_name,
        short_help=f"Bind '{project_name}' into <project-root> (alias for "
        f"`library bind {project_name} ...`).",
    )
    @click.argument("project_dir", type=click.Path(file_okay=False, path_type=Path))
    @click.option(
        "--unbind",
        is_flag=True,
        help="Reverse: move the project tree back into home.",
    )
    @click.option("--dry-run", is_flag=True)
    @click.option("--yes", "-y", is_flag=True)
    @click.pass_context
    def _shorthand(ctx, project_dir, unbind, dry_run, yes):
        ctx.invoke(
            library_bind,
            project=project_name,
            project_dir=project_dir,
            unbind=unbind,
            dry_run=dry_run,
            yes=yes,
        )

    return _shorthand


@click.group(cls=_LibraryGroup, context_settings=CONTEXT_SETTINGS)
def library() -> None:
    """Library-tree management.

    \b
    Common workflow:
      list       — see what's in the library
      open-urls  — open paper URLs in a browser (--watch auto-imports PDFs)
      refresh    — reconcile + regenerate symlinks (+ optional rsync)
    """


def _library_link_options(f):
    f = click.argument("project_dir", type=click.Path(file_okay=False, path_type=Path))(
        f
    )
    f = click.option(
        "--force", is_flag=True, help="Replace an existing symlink/directory."
    )(f)
    f = click.option("--dry-run", is_flag=True)(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    return f


@library.command("link-project-tree")
@_library_link_options
def library_link_project_tree(project_dir, force, dry_run, yes):
    """Symlink a project's .scitex/scholar/library to the home library.

    \b
    Example:
      $ scitex-scholar library link-project-tree .
    """
    return _do_link_project_tree(project_dir, force, dry_run, yes)


def _do_link_project_tree(project_dir, force, dry_run, yes):
    if dry_run:
        click.echo(
            f"DRY RUN — would symlink {project_dir}/.scitex/scholar/library "
            f"-> ~/.scitex/scholar/library (force={force})"
        )
        return 0
    from ..cli._project_tree import link_project_tree

    try:
        link_project_tree(Path(project_dir), force=force)
        sys.exit(0)
    except (FileNotFoundError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc


def _library_materialize_options(f):
    f = click.argument("link_path", type=click.Path(path_type=Path))(f)
    f = click.option(
        "--bib",
        required=True,
        type=click.Path(dir_okay=False, path_type=Path),
        help="BibTeX file whose DOIs select papers.",
    )(f)
    f = click.option("--dry-run", is_flag=True)(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    return f


@library.command("materialize")
@_library_materialize_options
def library_materialize(link_path, bib, dry_run, yes):
    """Replace a library-symlink with a bib-filtered real directory.

    \b
    Example:
      $ scitex-scholar library materialize .scitex/scholar/library --bib refs.bib
    """
    return _do_materialize(link_path, bib, dry_run, yes)


def _do_materialize(link_path, bib, dry_run, yes):
    if dry_run:
        click.echo(f"DRY RUN — would materialize {link_path} from {bib}")
        return 0
    from ..cli._materialize import materialize

    try:
        n, _ = materialize(Path(link_path), Path(bib))
        sys.exit(0 if n > 0 else 1)
    except (FileNotFoundError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc


def _library_dematerialize_options(f):
    f = click.argument("path", type=click.Path(file_okay=False, path_type=Path))(f)
    f = click.option(
        "--target",
        default=None,
        type=click.Path(file_okay=False, path_type=Path),
        help="Symlink target (default: ~/.scitex/scholar/library).",
    )(f)
    f = click.option("--dry-run", is_flag=True)(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    return f


@library.command("dematerialize")
@_library_dematerialize_options
def library_dematerialize(path, target, dry_run, yes):
    """Replace a materialized library directory with a symlink.

    \b
    Example:
      $ scitex-scholar library dematerialize .scitex/scholar/library
    """
    return _do_dematerialize(path, target, dry_run, yes)


def _do_dematerialize(path, target, dry_run, yes):
    if dry_run:
        click.echo(
            f"DRY RUN — would dematerialize {path} -> {target or '~/.scitex/scholar/library'}"
        )
        return 0
    from ..cli._materialize import dematerialize

    try:
        dematerialize(Path(path), target=Path(target) if target else None)
        sys.exit(0)
    except (FileNotFoundError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc


# ----- library db ----------------------------------------------------------


@library.group("db", context_settings=CONTEXT_SETTINGS)
def library_db() -> None:
    """Manage the library SQLite index."""


def _default_library_root() -> Path:
    return Path("~/.scitex/scholar/library").expanduser().resolve()


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
    root = library_root or _default_library_root()
    if dry_run:
        click.echo(f"DRY RUN — would (re)build index at {root}")
        return
    from ..storage import _library_index as idx

    n = idx.build(root, verbose=verbose)
    if as_json:
        click.echo(_json.dumps({"indexed": n, "db_path": str(idx.db_path(root))}))
    else:
        click.echo(f"{n} papers indexed at {idx.db_path(root)}")


@library_db.command("migrate")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def library_db_migrate(library_root, dry_run, yes):
    """Apply pending schema migrations.

    \b
    Example:
      $ scitex-scholar library db migrate
    """
    root = library_root or _default_library_root()
    if dry_run:
        click.echo(f"DRY RUN — would migrate index at {root}")
        return
    from ..storage import _library_index as idx

    v = idx.migrate(root)
    click.echo(f"Schema version: {v}")


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

    root = library_root or _default_library_root()
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
    root = library_root or _default_library_root()
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
    root = library_root or _default_library_root()
    from ..storage._library_audit import audit, format_report

    report = audit(root)
    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
    else:
        click.echo(format_report(report))
    if strict and report.has_issues:
        sys.exit(1)


# `reconcile-projects` / `refresh-symlinks` were folded into
# `library refresh` (see below). The underlying helpers
# (`storage._project_reconcile.reconcile_projects` and
# `LibraryManager.update_symlink`) remain exported and are called
# directly by the umbrella.


# ----- library refresh (umbrella) ----------------------------------------


def _project_metadata_path(library_root: Path, project: str) -> Path:
    return library_root / project / "info" / "project_metadata.json"


def _load_project_metadata(library_root: Path, project: str) -> dict:
    p = _project_metadata_path(library_root, project)
    if not p.exists():
        return {}
    try:
        return _json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _save_project_metadata(library_root: Path, project: str, data: dict) -> None:
    p = _project_metadata_path(library_root, project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(data, indent=2, ensure_ascii=False))


# ----- library zotero (bidirectional migration) -------------------------


@library.group("zotero", context_settings=CONTEXT_SETTINGS)
def library_zotero():
    """Bidirectional Zotero migration (local SQLite, no API key).

    \b
    Import:  Zotero -> Scholar  (papers + collections + tags + PDFs)
    Export:  Scholar -> Zotero  (BibTeX + PDFs, ready for File > Import)
    Diff:    show what's in one but not the other
    """


@library_zotero.command("import")
@click.option("--project", default=None, help="Scholar project to import into.")
@click.option("--collection", default=None, help="Limit to one Zotero collection.")
@click.option("--tag", "tags", multiple=True, help="Filter by Zotero tag (repeatable).")
@click.option(
    "--match-all/--match-any",
    default=False,
    help="With --tag: require ALL tags (default: any).",
)
@click.option(
    "--no-pdfs",
    "include_pdfs",
    flag_value=False,
    default=True,
    help="Skip PDF copying (metadata only).",
)
@click.option("--limit", type=int, default=None, help="Max items to import.")
@click.option(
    "--dry-run", is_flag=True, help="Preview what would be imported; write nothing."
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Proceed without confirmation (required for a non-dry-run import).",
)
@click.option(
    "--db", default=None, help="Path to zotero.sqlite (auto-detect if omitted)."
)
def library_zotero_import(
    project, collection, tags, match_all, include_pdfs, limit, dry_run, yes, db
):
    """Import from local Zotero database into the Scholar library.

    \b
    Examples:
      $ scitex-scholar library zotero import --project neurovista --dry-run
      $ scitex-scholar library zotero import --project neurovista --yes
      $ scitex-scholar library zotero import --project neurovista --collection EEG --yes
    """
    if not project:
        raise click.UsageError("--project is required for Zotero import.")
    if not dry_run and not yes:
        raise click.UsageError(
            "library zotero import modifies the Scholar library. Re-run with "
            "--dry-run to preview, or --yes/-y to proceed."
        )
    from ..integration.zotero import ZoteroLocalMigrator

    mig = ZoteroLocalMigrator(db_path=db, project=project)

    if collection:
        report = mig.import_collection(
            collection_name=collection, include_pdfs=include_pdfs, dry_run=dry_run
        )
    elif tags:
        report = mig.import_by_tags(
            tags=list(tags),
            match_all=match_all,
            include_pdfs=include_pdfs,
            dry_run=dry_run,
        )
    else:
        report = mig.import_all(limit=limit, include_pdfs=include_pdfs, dry_run=dry_run)

    verb = "Would import" if dry_run else "Imported"
    n = getattr(report, "total_imported", None)
    if n is None:
        n = getattr(report, "items_processed", "?")
    click.secho(f"{verb} {n} item(s) into project '{project}'.", fg="green")


@library_zotero.command("export")
@click.option("--project", default=None, help="Scholar project to export.")
@click.option(
    "--output",
    "output_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output dir (default: ~/.scitex/scholar/exports/zotero-<ts>/).",
)
@click.option(
    "--no-pdfs",
    "include_pdfs",
    flag_value=False,
    default=True,
    help="Skip bundling PDFs (BibTeX-only export).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview the output location; create nothing.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Proceed without confirmation (required to write the export).",
)
def library_zotero_export(project, output_dir, include_pdfs, dry_run, yes):
    """Export Scholar papers as a Zotero-importable package (BibTeX + PDFs).

    \b
    Examples:
      $ scitex-scholar library zotero export --project neurovista --dry-run
      $ scitex-scholar library zotero export --project neurovista --yes
      $ scitex-scholar library zotero export --project neurovista --output ~/zx --yes
    """
    if not project:
        raise click.UsageError("--project is required for Zotero export.")

    if output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = (
            _default_library_root().parent / "exports" / f"zotero-{project}-{ts}"
        )
    output_dir = Path(output_dir)

    if dry_run:
        click.echo(
            f"DRY RUN — would export project '{project}' "
            f"({'with' if include_pdfs else 'without'} PDFs) -> {output_dir}"
        )
        return
    if not yes:
        raise click.UsageError(
            "library zotero export writes files to disk. Re-run with "
            "--dry-run to preview, or --yes/-y to proceed."
        )

    from ..integration.zotero import ZoteroLocalMigrator

    mig = ZoteroLocalMigrator(project=project)
    output_dir.mkdir(parents=True, exist_ok=True)

    pkg = mig.export_for_import(
        project=project, output_dir=output_dir, include_pdfs=include_pdfs
    )
    bib = getattr(pkg, "bibtex_path", None) or getattr(pkg, "bib_path", None)
    n = getattr(pkg, "items_exported", None) or getattr(pkg, "n_papers", "?")
    click.secho(
        f"Exported {n} paper(s) -> {output_dir}\n  BibTeX: {bib}",
        fg="green",
    )


@library_zotero.command("diff")
@click.option("--project", default=None, help="Scholar project to compare.")
@click.option("--db", default=None, help="Path to zotero.sqlite (auto-detect).")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def library_zotero_diff(project, db, as_json):
    """Compare Zotero vs Scholar — show items present in one but not the other.

    \b
    Examples:
      $ scitex-scholar library zotero diff --project neurovista
      $ scitex-scholar library zotero diff --project neurovista --json
    """
    if not project:
        raise click.UsageError("--project is required.")
    from ..integration.zotero import ZoteroLocalMigrator

    mig = ZoteroLocalMigrator(db_path=db, project=project)
    diff = mig.diff() if hasattr(mig, "diff") else None
    if diff is None:
        raise click.ClickException(
            "ZoteroLocalMigrator has no .diff() — engine update required."
        )
    if as_json:
        click.echo(
            _json.dumps(getattr(diff, "to_dict", lambda: diff)(), indent=2, default=str)
        )
        return
    click.echo(
        f"Only-in-Zotero:  {len(getattr(diff, 'only_in_zotero', []) or [])}\n"
        f"Only-in-Scholar: {len(getattr(diff, 'only_in_scholar', []) or [])}\n"
        f"Both:            {len(getattr(diff, 'both', []) or [])}"
    )


@library.command("audit-files")
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option("--project", default=None, help="Limit to a single project.")
@click.option(
    "--rehash/--no-rehash",
    default=True,
    show_default=True,
    help="Recompute SHA-256 of every file on disk and verify against the "
    "stored entry. Disable for a fast presence-only audit.",
)
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def library_audit_files(library_root, project, rehash, as_json):
    """Verify recorded files vs disk state for every paper.

    \b
    For each MASTER entry, cross-references ``metadata.path.files``
    (role + sha256 + name) against what's actually in the directory.

    \b
    Reports:
      • missing       — recorded file not on disk
      • orphan        — file on disk with no record (role guessed from
                        prefix: 'supple-' / 'additional-' / main PDF)
      • hash_mismatch — name matches but content differs (file replaced)

    \b
    Examples:
      $ scitex-scholar library audit-files
      $ scitex-scholar library audit-files --project neurovista --no-rehash
      $ scitex-scholar library audit-files --json
    """
    import hashlib

    root = Path(library_root) if library_root else _default_library_root()
    master = root / "MASTER"
    if not master.is_dir():
        raise click.ClickException(f"MASTER dir not found: {master}")

    def _sha(p: Path) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _guess_role(name: str) -> str:
        if name.startswith("supple-"):
            return "supplementary"
        if name.startswith("additional-"):
            return "additional"
        if name.lower().endswith(".pdf"):
            return "main"
        return "unknown"

    report: dict = {
        "papers": [],
        "totals": {"papers": 0, "missing": 0, "orphan": 0, "hash_mismatch": 0},
    }
    for entry_dir in sorted(master.iterdir()):
        if not entry_dir.is_dir():
            continue
        meta_file = entry_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            data = _json.loads(meta_file.read_text())
        except (OSError, ValueError):
            continue
        if project:
            projs = (data.get("container") or {}).get("projects") or []
            if project not in projs:
                continue

        recorded = (data.get("metadata", {}).get("path", {}).get("files")) or []
        recorded_by_name = {e["name"]: e for e in recorded if isinstance(e, dict)}
        on_disk = {
            p.name: p
            for p in entry_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() not in (".json", ".log")
            and p.name != "metadata.json"
        }

        missing, orphan, mismatch = [], [], []
        for name, entry in recorded_by_name.items():
            if name not in on_disk:
                missing.append(
                    {
                        "name": name,
                        "role": entry.get("role"),
                        "sha256": entry.get("sha256"),
                    }
                )
                continue
            if rehash and entry.get("sha256"):
                actual = _sha(on_disk[name])
                if actual != entry["sha256"]:
                    mismatch.append(
                        {
                            "name": name,
                            "role": entry.get("role"),
                            "recorded_sha": entry["sha256"],
                            "disk_sha": actual,
                        }
                    )
        for name in on_disk:
            if name not in recorded_by_name:
                orphan.append({"name": name, "guessed_role": _guess_role(name)})

        if missing or orphan or mismatch:
            report["papers"].append(
                {
                    "paper_id": entry_dir.name,
                    "missing": missing,
                    "orphan": orphan,
                    "hash_mismatch": mismatch,
                }
            )
        report["totals"]["papers"] += 1
        report["totals"]["missing"] += len(missing)
        report["totals"]["orphan"] += len(orphan)
        report["totals"]["hash_mismatch"] += len(mismatch)

    if as_json:
        click.echo(_json.dumps(report, indent=2, default=str))
        return

    t = report["totals"]
    click.echo(
        f"Scanned {t['papers']} papers. "
        f"missing={t['missing']} orphan={t['orphan']} "
        f"hash_mismatch={t['hash_mismatch']}"
    )
    for p in report["papers"][:30]:
        click.secho(f"  [{p['paper_id']}]", fg="yellow")
        for m in p["missing"]:
            click.echo(f"    MISSING       {m['name']} (role={m['role']})")
        for o in p["orphan"]:
            click.echo(
                f"    ORPHAN        {o['name']} (guessed_role={o['guessed_role']})"
            )
        for h in p["hash_mismatch"]:
            click.echo(f"    HASH_MISMATCH {h['name']}")
    if len(report["papers"]) > 30:
        click.echo(f"  ... and {len(report['papers']) - 30} more")


@library.command("refresh")
@click.argument("project", required=False)
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option(
    "--sync",
    "sync_hosts",
    multiple=True,
    help="rsync push to HOST after refresh. Repeatable: --sync a --sync b.",
)
@click.option(
    "--pull",
    is_flag=True,
    help="With --sync HOST: pull from HOST first, then refresh locally.",
)
@click.option("--delete", is_flag=True, help="Pass --delete to rsync.")
@click.option("--dry-run", is_flag=True, help="Preview only.")
@click.option("--json", "as_json", is_flag=True, help="JSON report.")
def library_refresh(project, library_root, sync_hosts, pull, delete, dry_run, as_json):
    """One-button maintenance: reconcile + refresh symlinks + optional sync.

    \b
    Runs in order:
      1. reconcile-projects  — sync ``container.projects`` with filesystem
                              symlinks
      2. refresh-symlinks    — regenerate readable names (PDF-NN_CC-...)
      3. (optional) sync     — rsync push (or --pull) per --sync HOST

    \b
    Each refresh is recorded in
    ``library/<project>/info/project_metadata.json`` as a
    ``last_refresh`` entry plus an appended ``syncs`` ledger.

    \b
    Examples:
      $ scitex-scholar library refresh
      $ scitex-scholar library refresh neurovista
      $ scitex-scholar library refresh neurovista --sync spartan
      $ scitex-scholar library refresh neurovista --sync a --sync b
      $ scitex-scholar library refresh neurovista --sync spartan --pull
    """
    import shutil
    import subprocess
    from datetime import datetime, timezone

    root = Path(library_root) if library_root else _default_library_root()
    started = datetime.now(timezone.utc)

    # 1) Reconcile container.projects vs symlinks (whole library; cheap).
    from ..storage._project_reconcile import reconcile_projects

    rec = reconcile_projects(root, dry_run=dry_run)

    # 2) Refresh symlinks: walk MASTER, call canonical update_symlink per
    #    (paper, project) pair. Limit to PROJECT if given.
    from ..config import ScholarConfig
    from ..storage._LibraryManager import LibraryManager

    cfg = ScholarConfig()
    cfg.library_dir = str(root)

    symlink_stats = {"updated": 0, "errors": 0}
    master = root / "MASTER"
    if master.is_dir():
        for entry_dir in sorted(master.iterdir()):
            if not entry_dir.is_dir():
                continue
            meta_file = entry_dir / "metadata.json"
            if not meta_file.exists():
                continue
            try:
                data = _json.loads(meta_file.read_text())
            except (OSError, ValueError):
                continue
            projects = (data.get("container") or {}).get("projects") or []
            if project:
                projects = [p for p in projects if p == project]
            for proj in projects:
                if dry_run:
                    symlink_stats["updated"] += 1
                    continue
                try:
                    lm = LibraryManager(project=proj, config=cfg)
                    lm.update_symlink(
                        master_storage_path=entry_dir,
                        project=proj,
                        metadata=data,
                    )
                    symlink_stats["updated"] += 1
                except Exception:
                    symlink_stats["errors"] += 1

    # 3) Sync (optional). Reuse the same path-resolution rules as
    #    `library sync`: detect bind, mirror to ~/proj/<p>/... when bound.
    sync_results: list[dict] = []
    if sync_hosts:
        if shutil.which("rsync") is None:
            raise click.ClickException("rsync not found in PATH")
        if not project:
            raise click.ClickException(
                "--sync requires PROJECT (per-project rsync only)"
            )

        # Data always lives under the home library now (bind is just a
        # one-way view-symlink, no relocation).
        src = root / project
        remote_path = f".scitex/scholar/library/{project}/"

        rsync_flags = [
            "-av",
            "--info=progress2",
            "--human-readable",
            "--copy-links",
        ]
        if delete:
            rsync_flags.append("--delete")
        if dry_run:
            rsync_flags.append("--dry-run")

        for host in sync_hosts:
            t0 = datetime.now(timezone.utc)
            src_arg = f"{src}/"
            remote_arg = f"{host}:{remote_path}"
            cmd = (
                ["rsync", *rsync_flags, remote_arg, src_arg]
                if pull
                else ["rsync", *rsync_flags, src_arg, remote_arg]
            )
            click.echo("Running: " + " ".join(cmd))
            rc = subprocess.run(cmd).returncode
            sync_results.append(
                {
                    "ts": t0.isoformat() + "Z",
                    "host": host,
                    "direction": "pull" if pull else "push",
                    "rc": rc,
                    "duration_sec": (datetime.now(timezone.utc) - t0).total_seconds(),
                    "delete": delete,
                    "dry_run": dry_run,
                }
            )

    # 4) Persist per-project metadata. If no PROJECT was given, write to
    #    each project that participated.
    refresh_record = {
        "ts": started.isoformat() + "Z",
        "duration_sec": (datetime.now(timezone.utc) - started).total_seconds(),
        "reconcile": {
            "updated": len(rec.updated),
            "unchanged": rec.unchanged,
            "broken_symlinks": len(rec.broken_symlinks),
        },
        "symlinks": symlink_stats,
        "dry_run": dry_run,
    }
    affected_projects = (
        [project]
        if project
        else sorted(
            {
                proj
                for entry_dir in master.iterdir()
                if entry_dir.is_dir() and (entry_dir / "metadata.json").exists()
                for proj in (
                    (
                        _json.loads((entry_dir / "metadata.json").read_text()).get(
                            "container"
                        )
                        or {}
                    ).get("projects")
                    or []
                )
                if not dry_run  # don't churn metadata in dry-run
            }
        )
    )

    if not dry_run:
        for proj in affected_projects:
            pm = _load_project_metadata(root, proj)
            pm.setdefault("project", proj)
            pm.setdefault("created_at", started.isoformat() + "Z")
            pm["last_refresh"] = refresh_record
            if sync_results and (project is None or project == proj):
                pm.setdefault("syncs", []).extend(sync_results)
            _save_project_metadata(root, proj, pm)

    report = {
        "library_root": str(root),
        "project": project,
        "reconcile": rec.to_dict(),
        "symlinks": symlink_stats,
        "syncs": sync_results,
        "metadata_written": [] if dry_run else affected_projects,
    }
    if as_json:
        click.echo(_json.dumps(report, indent=2, default=str))
        return

    click.secho("Refresh complete.", fg="green")
    click.echo(
        f"  reconcile: updated={len(rec.updated)} unchanged={rec.unchanged} "
        f"broken_symlinks={len(rec.broken_symlinks)}"
    )
    click.echo(
        f"  symlinks:  updated={symlink_stats['updated']} "
        f"errors={symlink_stats['errors']}"
    )
    for s in sync_results:
        color = "green" if s["rc"] == 0 else "red"
        click.secho(
            f"  sync {s['direction']:<4} {s['host']}: rc={s['rc']} "
            f"({s['duration_sec']:.1f}s)",
            fg=color,
        )
    if not dry_run and affected_projects:
        click.echo(f"  metadata: wrote {len(affected_projects)} project_metadata.json")


# ----- library export ----------------------------------------------------


def _resolve_export_dir(library_root: Path, project: str) -> Path:
    """Exports always live under the home tree at ``~/.scitex/scholar/exports/``.

    (Bind no longer relocates data, so there's no project-repo location
    to special-case.)
    """
    return library_root.parent / "exports"


def _project_papers(library_root: Path, project: str):
    """Yield (paper_id, paper_dir, metadata_dict) for every paper in PROJECT."""
    master = library_root / "MASTER"
    if not master.is_dir():
        return
    for entry_dir in sorted(master.iterdir()):
        if not entry_dir.is_dir():
            continue
        meta_file = entry_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            data = _json.loads(meta_file.read_text())
        except (OSError, ValueError):
            continue
        projects = (data.get("container") or {}).get("projects") or []
        if project not in projects:
            continue
        yield entry_dir.name, entry_dir, data


def _bibtex_escape(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
        .strip()
    )


def _metadata_to_bibtex(paper_id: str, data: dict) -> str:
    md = data.get("metadata", {}) or {}
    basic = md.get("basic", {}) or {}
    pub = md.get("publication", {}) or {}
    id_ = md.get("id", {}) or {}

    authors = basic.get("authors") or []
    first_author = "Unknown"
    if authors:
        first = authors[0]
        if isinstance(first, str):
            first_author = first.replace(",", " ").split()[-1]
        elif isinstance(first, dict):
            first_author = (
                first.get("family")
                or first.get("last")
                or first.get("name")
                or "Unknown"
            )
    year = basic.get("year") or "0000"
    key = f"{first_author}{year}_{paper_id}"

    fields = {
        "title": basic.get("title"),
        "author": (
            " and ".join(authors) if isinstance(authors, list) and authors else None
        ),
        "year": year,
        "journal": pub.get("journal") or basic.get("venue"),
        "volume": pub.get("volume"),
        "number": pub.get("issue") or pub.get("number"),
        "pages": pub.get("pages"),
        "doi": id_.get("doi"),
        "url": (md.get("url") or {}).get("doi"),
        "abstract": basic.get("abstract"),
    }
    lines = [f"@article{{{key},"]
    for k, v in fields.items():
        if v in (None, "", []):
            continue
        lines.append(f"  {k} = {{{_bibtex_escape(v)}}},")
    lines.append("}")
    return "\n".join(lines)


def _export_bibtex(library_root: Path, project: str, out: Path) -> int:
    n = 0
    with out.open("w", encoding="utf-8") as f:
        f.write("% Exported by scitex-scholar library export\n")
        f.write(f"% project = {project}\n")
        f.write(f"% generated_at = {datetime.now(timezone.utc).isoformat()}\n\n")
        for paper_id, _, data in _project_papers(library_root, project):
            f.write(_metadata_to_bibtex(paper_id, data))
            f.write("\n\n")
            n += 1
    return n


def _export_tarball(library_root: Path, project: str, out: Path) -> int:
    import tarfile

    home_proj = library_root / project
    if not home_proj.exists():
        raise click.ClickException(f"Project dir missing: {home_proj}")
    n = 0
    # dereference=True copies PDF contents through symlinks → self-contained.
    with tarfile.open(out, "w:gz", dereference=True) as tar:
        for path in sorted(home_proj.rglob("*")):
            tar.add(path, arcname=str(Path(project) / path.relative_to(home_proj)))
            n += 1
        # Also add the project root itself (rglob doesn't include it).
        tar.add(home_proj, arcname=project, recursive=False)
    return n


def _export_flat_pdfs(library_root: Path, project: str, out: Path) -> int:
    import shutil
    import tarfile
    import tempfile

    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / project
        staging.mkdir(parents=True)
        for paper_id, paper_dir, data in _project_papers(library_root, project):
            for pdf in paper_dir.glob("*.pdf"):
                # Use the existing readable name on disk if available.
                shutil.copy2(pdf, staging / pdf.name)
                n += 1
        with tarfile.open(out, "w:gz") as tar:
            tar.add(staging, arcname=project)
    return n


@library.command("export")
@click.argument("project")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["bibtex", "tarball", "flat-pdfs", "zotero"]),
    default="tarball",
    show_default=True,
    help="bibtex (.bib only), tarball (full tree, follows symlinks), "
    "flat-pdfs (PDFs in one dir tarred), zotero (RDF — not implemented).",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(path_type=Path),
    help="Output path. Default: <export_dir>/<project>-<ts>.<ext>.",
)
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option("--dry-run", is_flag=True, help="Preview only.")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Proceed without confirmation (required to write the export).",
)
def library_export(project, fmt, output, library_root, dry_run, yes):
    """Export PROJECT in a portable format.

    \b
    Default location:
      <project-dir>/.scitex/scholar/exports/<project>-<ts>.<ext>  (when bound)
      ~/.scitex/scholar/exports/<project>-<ts>.<ext>              (otherwise)

    \b
    Examples:
      $ scitex-scholar library export neurovista --dry-run
      $ scitex-scholar library export neurovista --yes
      $ scitex-scholar library export neurovista --format flat-pdfs -o /tmp/x.tar.gz --yes
    """
    from datetime import datetime, timezone

    root = Path(library_root) if library_root else _default_library_root()
    home_proj = root / project
    if not home_proj.exists():
        raise click.ClickException(f"Project not found: {home_proj}")

    if output is None:
        export_dir = _resolve_export_dir(root, project)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        ext = {
            "bibtex": "bib",
            "tarball": "tar.gz",
            "flat-pdfs": "tar.gz",
            "zotero": "rdf",
        }[fmt]
        out_path = export_dir / f"{project}-{ts}.{ext}"
    else:
        out_path = Path(output)

    if dry_run:
        click.echo(f"DRY RUN — would export {fmt} -> {out_path}")
        return
    if not yes:
        raise click.UsageError(
            f"library export writes {out_path}. Re-run with --dry-run to "
            "preview, or --yes/-y to proceed."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "bibtex":
        n = _export_bibtex(root, project, out_path)
        click.secho(f"Wrote {n} BibTeX entries -> {out_path}", fg="green")
    elif fmt == "tarball":
        n = _export_tarball(root, project, out_path)
        click.secho(f"Wrote {n} files -> {out_path}", fg="green")
    elif fmt == "flat-pdfs":
        n = _export_flat_pdfs(root, project, out_path)
        click.secho(f"Wrote {n} PDFs -> {out_path}", fg="green")
    elif fmt == "zotero":
        raise click.ClickException("zotero export not yet implemented")


# ----- library bind ------------------------------------------------------


@library.command("bind")
@click.argument("project")
@click.argument("project_dir", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--unbind",
    is_flag=True,
    help="Reverse: move the project tree back into the home library.",
)
@click.option("--dry-run", is_flag=True, help="Show actions without performing.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def library_bind(project, project_dir, unbind, dry_run, yes):
    """Add a project-local view of the home library via one symlink.

    \b
    Effect:
      <project-dir>/.scitex/scholar/library/<project>
        ─→  ~/.scitex/scholar/library/<project>

    \b
    No data is moved; no MASTER passthrough is needed (relative
    ``../MASTER/<id>`` symlinks inside the home dir resolve correctly
    because Linux follows the symlink to its real target before resolving
    relative paths).

    \b
    With --unbind: just remove the symlink (target is left untouched).

    \b
    Examples:
      $ scitex-scholar library bind neurovista ~/proj/neurovista
      $ scitex-scholar library bind neurovista ~/proj/neurovista --unbind
    """
    home_root = _default_library_root()
    home_proj = home_root / project
    repo_lib_root = Path(project_dir).expanduser() / ".scitex/scholar/library"
    repo_link = repo_lib_root / project

    if not unbind:
        if not home_proj.exists():
            raise click.ClickException(f"No project at {home_proj}")
        if repo_link.exists() or repo_link.is_symlink():
            raise click.ClickException(
                f"Already exists: {repo_link} (use --unbind to remove)"
            )
        click.echo(f"Will create  {repo_link}")
        click.echo(f"          -> {home_proj}")
        if dry_run:
            return
        if not yes:
            raise click.UsageError(
                "library bind creates a symlink. Re-run with --dry-run to "
                "preview, or --yes/-y to proceed."
            )
        repo_lib_root.mkdir(parents=True, exist_ok=True)
        repo_link.symlink_to(home_proj.resolve())
        click.secho("Bound (one symlink, no data moved).", fg="green")
        return

    # Unbind.
    if not repo_link.is_symlink():
        raise click.ClickException(f"{repo_link} is not a symlink (nothing to unbind)")
    click.echo(f"Will remove  {repo_link} (target stays: {repo_link.resolve()})")
    if dry_run:
        return
    if not yes:
        raise click.UsageError(
            "library bind --unbind removes a symlink. Re-run with --dry-run "
            "to preview, or --yes/-y to proceed."
        )
    repo_link.unlink()
    click.secho("Unbound.", fg="green")


# ----- library sync ------------------------------------------------------


@library.command("sync")
@click.argument("host")
@click.option("--project", default=None, help="Limit to a single project.")
@click.option(
    "--pull",
    is_flag=True,
    help="Pull from host to local (default: push local to host).",
)
@click.option("--delete", is_flag=True, help="Pass --delete to rsync (mirror).")
@click.option("--dry-run", is_flag=True, help="rsync --dry-run.")
@click.option(
    "--copy-links/--preserve-links",
    "copy_links",
    default=True,
    help="--copy-links (rsync -L) follows symlinks (self-contained remote, "
    "default). --preserve-links keeps them as symlinks.",
)
@click.option(
    "--remote-path",
    default=None,
    help="Remote path (relative to remote $HOME, or absolute starting with "
    "'/'). Default: '.scitex/scholar/library/[<project>/]'.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Proceed without confirmation (required for a non-dry-run sync).",
)
def library_sync(host, project, pull, delete, dry_run, copy_links, remote_path, yes):
    """rsync the library to/from a remote HOST.

    \b
    Behavior:
      • If the project is bound (`library bind`), source/target is the
        project repo's `.scitex/scholar/library/` on each side, mapped to
        the same `~/proj/<project>/...` path on the remote.
      • Otherwise, mirrors `~/.scitex/scholar/library/[<project>/]` on
        each side.

    \b
    Examples:
      $ scitex-scholar library sync spartan --project neurovista --dry-run
      $ scitex-scholar library sync spartan --project neurovista
      $ scitex-scholar library sync spartan --pull --project neurovista
    """
    import shutil
    import subprocess

    if shutil.which("rsync") is None:
        raise click.ClickException("rsync not found in PATH")

    home_root = _default_library_root()

    # Data always lives under the home library (bind = view-only symlink),
    # so source/target paths are straightforward.
    if project:
        src = home_root / project
        default_remote = f".scitex/scholar/library/{project}/"
    else:
        src = home_root
        default_remote = ".scitex/scholar/library/"

    # --remote-path overrides the default. Trailing slash is normalized so
    # rsync syncs into the directory rather than nesting it under itself.
    if remote_path:
        chosen = remote_path if remote_path.endswith("/") else remote_path + "/"
        remote_path = chosen
    else:
        remote_path = default_remote

    if not src.exists():
        raise click.ClickException(f"Source missing: {src}")

    rsync_flags = ["-av", "--info=progress2", "--human-readable"]
    if copy_links:
        rsync_flags.append("--copy-links")
    else:
        rsync_flags.append("--links")
    if delete:
        rsync_flags.append("--delete")
    if dry_run:
        rsync_flags.append("--dry-run")

    src_arg = f"{src}/"
    remote_arg = f"{host}:{remote_path}"

    if pull:
        cmd = ["rsync", *rsync_flags, remote_arg, src_arg]
    else:
        cmd = ["rsync", *rsync_flags, src_arg, remote_arg]

    click.echo("Running: " + " ".join(cmd))
    if dry_run:
        click.secho("(dry-run — no changes written)", fg="yellow")
    elif not yes:
        raise click.UsageError(
            "library sync transfers files over rsync. Re-run with --dry-run "
            "to preview, or --yes/-y to proceed."
        )
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise click.ClickException(f"rsync exited {rc}")
    click.secho("Done.", fg="green")


# ----- library open-urls --------------------------------------------------


@library.command("open-urls")
@click.argument("project")
@click.option(
    "--all",
    "open_all",
    is_flag=True,
    help="Open every paper in the project (default: only those without a PDF).",
)
@click.option("--profile", default=None, help="Browser profile name (default: system).")
@click.option("--headless", is_flag=True, help="Headless browser (testing).")
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option(
    "--watch",
    is_flag=True,
    help=(
        "Watch the download dir during the session and auto-import new "
        "PDFs. Unmatched PDFs are moved to "
        "library/downloads/unmatched/<project>/."
    ),
)
@click.option(
    "--watch-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to watch (default: ~/Downloads).",
)
@click.option("--dry-run", is_flag=True, help="List URLs; do not open browser.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def library_open_urls(
    project,
    open_all,
    profile,
    headless,
    library_root,
    watch,
    watch_dir,
    dry_run,
    as_json,
):
    """Open per-paper URLs in a browser for PROJECT.

    \b
    Smart URL pick (OpenURL → publisher → DOI). Membership is read from
    ``container.projects``; run ``library reconcile-projects`` first if
    the field is stale.

    \b
    With ``--watch``, downloaded PDFs are matched (filename → PDF /Title →
    DOI on page 1) and moved into MASTER. Unmatched PDFs go to
    ``library/downloads/unmatched/<project>/``.

    \b
    Examples:
      $ scitex-scholar library open-urls neurovista
      $ scitex-scholar library open-urls neurovista --watch
      $ scitex-scholar library open-urls neurovista --watch --watch-dir ~/Downloads
      $ scitex-scholar library open-urls neurovista --dry-run --json
    """
    root = Path(library_root) if library_root else _default_library_root()
    papers = _gather_project_papers(root, project, open_all=open_all)

    if dry_run or as_json:
        from ..cli._url_utils import get_best_url

        entries = []
        for p in papers:
            url = get_best_url(
                openurl_resolved=p.get("openurl_resolved"),
                url_publisher=p.get("url_publisher"),
                url_doi=p.get("url_doi"),
                doi=p.get("doi"),
            )
            entries.append(
                {
                    "paper_id": p["paper_id"],
                    "first_author": p.get("first_author"),
                    "year": p.get("year"),
                    "journal": p.get("journal"),
                    "title": p.get("title"),
                    "url": url,
                    "has_pdf": p["has_pdf"],
                }
            )
        if as_json:
            click.echo(
                _json.dumps(
                    {"project": project, "count": len(entries), "papers": entries},
                    indent=2,
                    default=str,
                )
            )
        else:
            click.echo(
                f"Project '{project}': {len(entries)} paper(s) "
                f"({'all' if open_all else 'missing-PDF only'})"
            )
            for e in entries:
                parts = [
                    str(x)
                    for x in (
                        e.get("first_author"),
                        e.get("year"),
                        e.get("journal"),
                    )
                    if x
                ]
                label = " ".join(parts) if parts else e["paper_id"]
                click.echo(f"  {label:<40}  {e['url'] or '(no URL)'}")
        return

    if not papers:
        click.echo(f"No papers to open for project '{project}'.")
        return

    if watch:
        from ..cli.open_browser_monitored import open_browser_with_monitoring
        from ..config import ScholarConfig

        cfg = ScholarConfig()
        unmatched = root / "downloads" / "unmatched" / project
        watch_path = (
            Path(watch_dir).expanduser() if watch_dir else Path.home() / "Downloads"
        )
        open_browser_with_monitoring(
            papers,
            project=project,
            config=cfg,
            profile=profile,
            downloads_dir=watch_path,
            unmatched_dir=unmatched,
        )
        return

    from ..cli.open_browser import open_browser_with_urls

    open_browser_with_urls(papers, profile=profile, headless=headless)


# ----- library list -------------------------------------------------------


@library.command("list")
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option("-v", "--verbose", count=True, help="-v per-paper; -vv +URL; -vvv full.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
@click.argument("project", required=False)
def library_list(library_root, verbose, as_json, project):
    """List projects and their paper counts.

    \b
    Without PROJECT: list every project's totals.
    With PROJECT name: show only that project (auto-verbose unless --json).

    \b
    Verbosity:
      (none)  project, total, downloaded
      -v      + per-paper paper_id and title
      -vv     + URL and PDF flag
      -vvv    + DOI and full container.projects

    \b
    Examples:
      $ scitex-scholar library list
      $ scitex-scholar library list neurovista
      $ scitex-scholar library list -vv
      $ scitex-scholar library list --json
    """
    root = Path(library_root) if library_root else _default_library_root()
    if project and verbose == 0 and not as_json:
        verbose = 1
    summary = _summarize_projects(root, verbose=verbose)

    if project:
        summary["projects"] = [p for p in summary["projects"] if p["name"] == project]
        if not summary["projects"]:
            click.echo(
                f"Project '{project}' has no entries (or doesn't exist) under {root}."
            )
            return

    if as_json:
        click.echo(_json.dumps(summary, indent=2, default=str))
        return

    if not summary["projects"]:
        click.echo(f"No projects found under {root}.")
        return

    for proj in summary["projects"]:
        click.echo(
            f"{proj['name']:<24} total={proj['total']:>3}  "
            f"downloaded={proj['downloaded']:>3}  missing={proj['missing']:>3}"
        )
        if verbose >= 1:
            for p in proj["papers"]:
                line = f"    {p['paper_id']}  {(p.get('title') or '')[:80]}"
                click.echo(line)
                if verbose >= 2:
                    click.echo(
                        f"        url={p.get('url') or '(none)'}  has_pdf={p['has_pdf']}"
                    )
                if verbose >= 3:
                    click.echo(
                        f"        doi={p.get('doi') or '(none)'}  "
                        f"projects={p.get('projects')}"
                    )


def _gather_project_papers(
    library_root: Path, project: str, *, open_all: bool
) -> list[dict]:
    """Collect papers in ``project`` from MASTER metadata.

    Filtering:
      * project membership: ``container.projects`` contains ``project``
      * default: only entries with **no** ``*.pdf`` in the MASTER entry dir
      * with ``open_all=True``: every project member
    """
    master = Path(library_root) / "MASTER"
    out: list[dict] = []
    if not master.is_dir():
        return out

    for entry_dir in sorted(master.iterdir()):
        if not entry_dir.is_dir():
            continue
        meta_file = entry_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            data = _json.loads(meta_file.read_text())
        except (OSError, ValueError):
            continue

        projects = (data.get("container") or {}).get("projects") or []
        if project not in projects:
            continue

        has_pdf = bool(list(entry_dir.glob("*.pdf")))
        if not open_all and has_pdf:
            continue

        meta = data.get("metadata", {}) or {}
        basic = meta.get("basic", {}) or {}
        url = meta.get("url", {}) or {}
        publication = meta.get("publication", {}) or {}

        # Derive a short last-name for the first author.
        authors = basic.get("authors") or []
        first_author = ""
        if isinstance(authors, list) and authors:
            first = authors[0]
            if isinstance(first, str):
                # "Elliot H. Smith" -> "Smith"; "Smith E.H." -> "Smith"
                tokens = first.replace(",", " ").split()
                first_author = tokens[-1] if tokens else first
            elif isinstance(first, dict):
                first_author = (
                    first.get("family") or first.get("last") or first.get("name") or ""
                )

        out.append(
            {
                "paper_id": entry_dir.name,
                "title": basic.get("title"),
                "year": basic.get("year"),
                "doi": (meta.get("id") or {}).get("doi"),
                "first_author": first_author,
                "journal": (
                    publication.get("journal_short")
                    or publication.get("journal")
                    or basic.get("venue")
                    or ""
                ),
                "url_doi": url.get("doi"),
                "url_publisher": url.get("publisher"),
                "openurl_resolved": url.get("openurl_resolved", []) or [],
                "pdf_urls": url.get("pdfs", []) or [],
                "has_pdf": has_pdf,
            }
        )
    return out


def _summarize_projects(library_root: Path, *, verbose: int = 0) -> dict:
    """Build a per-project summary by reading every MASTER metadata.json.

    Returns ``{"projects": [{name, total, downloaded, missing, papers: [...]}]}``.
    The ``papers`` list is populated only when ``verbose >= 1``.
    """
    from collections import defaultdict

    from ..cli._url_utils import get_best_url

    master = Path(library_root) / "MASTER"
    by_project: dict[str, list[dict]] = defaultdict(list)
    if not master.is_dir():
        return {"projects": []}

    for entry_dir in sorted(master.iterdir()):
        if not entry_dir.is_dir():
            continue
        meta_file = entry_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            data = _json.loads(meta_file.read_text())
        except (OSError, ValueError):
            continue

        container = data.get("container") or {}
        projects = list(container.get("projects") or [])
        if not projects:
            continue

        has_pdf = bool(list(entry_dir.glob("*.pdf")))
        meta = data.get("metadata", {}) or {}
        url_obj = meta.get("url", {}) or {}
        record = {
            "paper_id": entry_dir.name,
            "title": (meta.get("basic") or {}).get("title"),
            "doi": (meta.get("id") or {}).get("doi"),
            "has_pdf": has_pdf,
            "projects": projects,
            "url": get_best_url(
                openurl_resolved=url_obj.get("openurl_resolved"),
                url_publisher=url_obj.get("publisher"),
                url_doi=url_obj.get("doi"),
                doi=(meta.get("id") or {}).get("doi"),
            ),
        }
        for p in projects:
            by_project[p].append(record)

    out = []
    for name in sorted(by_project):
        papers = by_project[name]
        downloaded = sum(1 for p in papers if p["has_pdf"])
        out.append(
            {
                "name": name,
                "total": len(papers),
                "downloaded": downloaded,
                "missing": len(papers) - downloaded,
                "papers": papers if verbose >= 1 else [],
            }
        )
    return {"projects": out}


# ----- library dedupe -----------------------------------------------------


@library.command("dedupe")
@click.option(
    "--library-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Library root (default: ~/.scitex/scholar/library).",
)
@click.option(
    "--dry-run",
    "mode",
    flag_value="dry-run",
    default=True,
    help="Preview the dedupe plan (default). Exit non-zero if conflicts exist.",
)
@click.option(
    "--apply",
    "mode",
    flag_value="apply",
    help="Quarantine duplicate-DOI losers to MASTER_quarantine/.",
)
@click.option(
    "--hard-delete",
    is_flag=True,
    help="With --apply, delete losers instead of quarantining (irreversible).",
)
def library_dedupe(library_root, mode, hard_delete):
    """Resolve duplicate-DOI entries in MASTER (fail-loud).

    Wraps the public ``storage._library_dedupe`` planner so a production
    library-sync cron can gate on it without importing a private module.

    \b
    Exit codes (a cron pre-sync gate depends on these):
      dry-run : 0 if the plan is empty, non-zero if duplicates need resolving.
      --apply : 0 once the library reaches a clean state (duplicates
                quarantined, or none to begin with); non-zero only if
                conflicts remain unresolved or an error occurs.

    \b
    Examples:
      $ scitex-scholar library dedupe --dry-run
      $ scitex-scholar library dedupe --apply
      $ scitex-scholar library dedupe --apply --hard-delete
    """
    root = library_root or _default_library_root()
    try:
        from ..storage._library_dedupe import (
            apply_plan,
            format_plan,
            plan_dedupe,
        )

        plan = plan_dedupe(root)

        if mode == "apply":
            moved = apply_plan(root, plan, hard_delete=hard_delete)
            verb = "deleted" if hard_delete else "quarantined"
            click.echo(f"{moved} entries {verb}.")
            residual = plan_dedupe(root)
            if residual.decisions:
                raise click.ClickException(
                    f"{len(residual.decisions)} duplicate-DOI group(s) remain "
                    "unresolved after apply."
                )
            return

        click.echo(format_plan(plan))
        if plan.decisions:
            sys.exit(1)
    except (click.ClickException, SystemExit):
        raise
    except Exception as exc:  # fail-loud — never swallow
        raise click.ClickException(f"library dedupe failed: {exc}") from exc
