#!/usr/bin/env python3
# File: src/scitex_scholar/__main__.py

"""Scholar CLI entry point — Click-based noun-verb subcommand interface.

Top-level groups:

- ``paper``   {fetch, fetch-batch}                       — fetch paper(s) into the library
- ``bibtex``  {import}                                   — import a BibTeX file
- ``pdf``     {highlight}                                — PDF post-processing
- ``library`` {link-project-tree, materialize, dematerialize, db}
- ``mcp``     {start, list-tools, doctor, install}       — MCP server commands
- ``skills``  {list, get, install}                       — bundled skill leaves
- ``list-python-apis``                                   — print public API names

Pre-1.3.0 top-level forms (``single``, ``parallel``, ``bibtex --bibtex …``,
``highlight``, ``link-project-tree``, ``materialize``, ``dematerialize``,
``db``) remain as **hidden deprecation aliases**: they parse cleanly,
emit a one-line yellow warning to stderr, and dispatch to the new handler.
"""

from __future__ import annotations

import asyncio
import json as _json
import sys
from pathlib import Path
from typing import Any

import click

# TODO(scitex-dev): import scitex_dev.click_helpers.CategorizedGroup once
# available; currently scitex-dev does not export it, so we fall back to
# plain click.Group.
try:  # pragma: no cover — depends on scitex-dev install
    from scitex_dev.click_helpers import CategorizedGroup  # type: ignore
except ImportError:  # pragma: no cover
    CategorizedGroup = click.Group  # type: ignore[assignment,misc]


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

COMMAND_CATEGORIES = [
    ("Paper", ["paper"]),
    ("Bibtex", ["bibtex"]),
    ("PDF", ["pdf"]),
    ("Library", ["library"]),
    ("Auth", ["auth"]),
    ("MCP", ["mcp"]),
    ("Skills", ["skills", "list-python-apis"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _warn_deprecated(old_form: str, new_form: str) -> None:
    """Emit a one-line yellow deprecation warning to stderr."""
    click.secho(
        f"DeprecationWarning: 'scitex-scholar {old_form}' is deprecated; "
        f"use 'scitex-scholar {new_form}' (will be removed in 1.4.0).",
        fg="yellow",
        err=True,
    )


def _print_command_help(
    cmd: click.Command, prefix: str, parent_ctx: click.Context
) -> None:
    """Recursively print help for a command and its subcommands."""
    click.echo(f"\n{'=' * 50}")
    click.echo(prefix)
    click.echo("=" * 50)
    sub_ctx = click.Context(cmd, info_name=prefix.split()[-1], parent=parent_ctx)
    click.echo(cmd.get_help(sub_ctx))
    if isinstance(cmd, click.Group):
        for sub_name, sub_cmd in sorted(cmd.commands.items()):
            if getattr(sub_cmd, "hidden", False):
                continue
            _print_command_help(sub_cmd, f"{prefix} {sub_name}", sub_ctx)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(
    cls=CategorizedGroup,
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    help=(
        "SciTeX Scholar — scientific literature management.\n\n"
        "Storage layout: ~/.scitex/scholar/library/MASTER/{8DIGITID}/ "
        "(canonical), {project}/ (symlinks)."
    ),
)
@click.version_option(None, "-V", "--version", package_name="scitex-scholar")
@click.option(
    "--help-recursive",
    is_flag=True,
    help="Show help for every command and subcommand.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON output where supported.",
)
@click.pass_context
def cli(ctx: click.Context, help_recursive: bool, as_json: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json

    if help_recursive:
        click.echo(cli.get_help(ctx))
        for name, cmd in sorted(cli.commands.items()):
            if getattr(cmd, "hidden", False):
                continue
            _print_command_help(cmd, f"scitex-scholar {name}", ctx)
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Group: paper
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def paper() -> None:
    """Operate on a paper / batch of papers."""


def _paper_fetch_options(f):
    f = click.option("--doi", default=None, help="DOI of the paper.")(f)
    f = click.option("--title", default=None, help="Paper title (resolves DOI).")(f)
    f = click.option("--project", default=None, help="Project name for organizing.")(f)
    f = click.option(
        "--browser-mode",
        type=click.Choice(["stealth", "interactive"]),
        default="stealth",
        show_default=True,
        help="Browser mode for PDF download.",
    )(f)
    f = click.option(
        "--chrome-profile",
        default="system",
        show_default=True,
        help="Chrome profile name.",
    )(f)
    f = click.option(
        "--force",
        "-f",
        is_flag=True,
        help="Force re-download even if files exist.",
    )(f)
    f = click.option("--dry-run", is_flag=True, help="Print plan without executing.")(f)
    f = click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive.")(
        f
    )
    f = click.option("--json", "as_json", is_flag=True, help="JSON output.")(f)
    return f


@paper.command("fetch")
@_paper_fetch_options
def paper_fetch(
    doi, title, project, browser_mode, chrome_profile, force, dry_run, yes, as_json
):
    """Fetch a single paper into the library.

    \b
    Example:
      $ scitex-scholar paper fetch --doi 10.1038/nature12373 --project demo
    """
    return _do_paper_fetch(
        doi=doi,
        title=title,
        project=project,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        force=force,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


def _do_paper_fetch(
    *, doi, title, project, browser_mode, chrome_profile, force, dry_run, yes, as_json
):
    if not doi and not title:
        raise click.UsageError("Either --doi or --title is required.")
    if dry_run:
        click.echo(
            f"DRY RUN — would fetch paper (doi={doi!r}, title={title!r}, "
            f"project={project!r}, browser_mode={browser_mode!r})"
        )
        return 0
    rc = asyncio.run(
        _run_paper_fetch_async(
            doi=doi,
            title=title,
            project=project,
            browser_mode=browser_mode,
            chrome_profile=chrome_profile,
            force=force,
        )
    )
    sys.exit(rc)


async def _run_paper_fetch_async(
    *, doi, title, project, browser_mode, chrome_profile, force
) -> int:
    from .pipelines.ScholarPipelineSingle import ScholarPipelineSingle

    doi_or_title = doi or title
    pipeline = ScholarPipelineSingle(
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
    )
    await pipeline.process_single_paper(
        doi_or_title=doi_or_title,
        project=project,
        force=force,
    )
    return 0


def _paper_fetch_batch_options(f):
    f = click.option("--dois", multiple=True, help="One or more DOIs (repeatable).")(f)
    f = click.option(
        "--titles", multiple=True, help="One or more titles (repeatable)."
    )(f)
    f = click.option("--project", default=None, help="Project name.")(f)
    f = click.option("--num-workers", type=int, default=4, show_default=True)(f)
    f = click.option(
        "--browser-mode",
        type=click.Choice(["stealth", "interactive"]),
        default="stealth",
        show_default=True,
    )(f)
    f = click.option("--chrome-profile", default="system", show_default=True)(f)
    f = click.option("--dry-run", is_flag=True)(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    f = click.option("--json", "as_json", is_flag=True)(f)
    return f


@paper.command("fetch-batch")
@_paper_fetch_batch_options
def paper_fetch_batch(
    dois,
    titles,
    project,
    num_workers,
    browser_mode,
    chrome_profile,
    dry_run,
    yes,
    as_json,
):
    """Fetch multiple papers in parallel.

    \b
    Example:
      $ scitex-scholar paper fetch-batch --dois 10.1/x --dois 10.2/y --project demo
    """
    return _do_paper_fetch_batch(
        dois=list(dois),
        titles=list(titles),
        project=project,
        num_workers=num_workers,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


def _do_paper_fetch_batch(
    *,
    dois,
    titles,
    project,
    num_workers,
    browser_mode,
    chrome_profile,
    dry_run,
    yes,
    as_json,
):
    if not dois and not titles:
        raise click.UsageError("Either --dois or --titles is required.")
    queries = [*dois, *titles]
    if dry_run:
        click.echo(
            f"DRY RUN — would fetch {len(queries)} papers in parallel "
            f"(num_workers={num_workers}, project={project!r})"
        )
        return 0
    rc = asyncio.run(
        _run_paper_fetch_batch_async(
            queries=queries,
            project=project,
            num_workers=num_workers,
            browser_mode=browser_mode,
            chrome_profile=chrome_profile,
        )
    )
    sys.exit(rc)


async def _run_paper_fetch_batch_async(
    *, queries, project, num_workers, browser_mode, chrome_profile
) -> int:
    from .pipelines.ScholarPipelineParallel import ScholarPipelineParallel

    pipeline = ScholarPipelineParallel(
        num_workers=num_workers,
        browser_mode=browser_mode,
        base_chrome_profile=chrome_profile,
    )
    await pipeline.process_papers_from_list_async(
        doi_or_title_list=queries,
        project=project,
    )
    return 0


# ---------------------------------------------------------------------------
# Group: bibtex
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def bibtex() -> None:
    """Operate on a BibTeX file."""


def _bibtex_import_options(f):
    f = click.option(
        "--bibtex",
        "bibtex_path",
        required=True,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Path to BibTeX file.",
    )(f)
    f = click.option("--project", default=None)(f)
    f = click.option(
        "--output", default=None, type=click.Path(dir_okay=False, path_type=Path)
    )(f)
    f = click.option("--num-workers", type=int, default=4, show_default=True)(f)
    f = click.option(
        "--browser-mode",
        type=click.Choice(["stealth", "interactive"]),
        default="stealth",
        show_default=True,
    )(f)
    f = click.option("--chrome-profile", default="system", show_default=True)(f)
    f = click.option("--dry-run", is_flag=True)(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    return f


@bibtex.command("import")
@_bibtex_import_options
def bibtex_import(
    bibtex_path,
    project,
    output,
    num_workers,
    browser_mode,
    chrome_profile,
    dry_run,
    yes,
):
    """Import & enrich every entry from a BibTeX file.

    \b
    Example:
      $ scitex-scholar bibtex import --bibtex refs.bib --project demo
    """
    return _do_bibtex_import(
        bibtex_path=bibtex_path,
        project=project,
        output=output,
        num_workers=num_workers,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        dry_run=dry_run,
        yes=yes,
    )


def _do_bibtex_import(
    *,
    bibtex_path,
    project,
    output,
    num_workers,
    browser_mode,
    chrome_profile,
    dry_run,
    yes,
):
    bibtex_path = Path(bibtex_path)
    if dry_run:
        click.echo(
            f"DRY RUN — would import {bibtex_path} (project={project!r}, "
            f"workers={num_workers}, output={output!r})"
        )
        return 0
    if not bibtex_path.exists():
        raise click.ClickException(f"BibTeX file not found: {bibtex_path}")
    rc = asyncio.run(
        _run_bibtex_import_async(
            bibtex_path=bibtex_path,
            project=project,
            output=output,
            num_workers=num_workers,
            browser_mode=browser_mode,
            chrome_profile=chrome_profile,
        )
    )
    sys.exit(rc)


async def _run_bibtex_import_async(
    *, bibtex_path, project, output, num_workers, browser_mode, chrome_profile
) -> int:
    from .pipelines.ScholarPipelineBibTeX import ScholarPipelineBibTeX

    pipeline = ScholarPipelineBibTeX(
        num_workers=num_workers,
        browser_mode=browser_mode,
        base_chrome_profile=chrome_profile,
    )
    await pipeline.process_bibtex_file_async(
        bibtex_path=bibtex_path,
        project=project,
        output_bibtex_path=output,
    )
    return 0


# ---------------------------------------------------------------------------
# Group: pdf
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def pdf() -> None:
    """PDF post-processing."""


def _pdf_highlight_options(f):
    f = click.argument("pdf_path", type=click.Path(dir_okay=False, path_type=Path))(f)
    f = click.option(
        "-o",
        "--output",
        default=None,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Output PDF (default: <input>.highlighted.pdf).",
    )(f)
    f = click.option("--model", default="claude-haiku-4-5-20251001", show_default=True)(
        f
    )
    f = click.option(
        "--stub", is_flag=True, help="Use offline keyword heuristic (no API calls)."
    )(f)
    f = click.option(
        "--dry-run", is_flag=True, help="Classify and print summary; do not write."
    )(f)
    f = click.option("--yes", "-y", is_flag=True)(f)
    f = click.option("--max-blocks", type=int, default=0)(f)
    f = click.option("--batch-size", type=int, default=25)(f)
    f = click.option("--min-chars", type=int, default=40)(f)
    f = click.option(
        "--labels-dump", default=None, type=click.Path(dir_okay=False, path_type=Path)
    )(f)
    f = click.option(
        "--labels-apply", default=None, type=click.Path(dir_okay=False, path_type=Path)
    )(f)
    return f


@pdf.command("highlight")
@_pdf_highlight_options
def pdf_highlight(
    pdf_path,
    output,
    model,
    stub,
    dry_run,
    yes,
    max_blocks,
    batch_size,
    min_chars,
    labels_dump,
    labels_apply,
):
    """Overlay semantic highlights on a PDF.

    \b
    Example:
      $ scitex-scholar pdf highlight paper.pdf --stub
    """
    return _do_pdf_highlight(
        pdf_path=pdf_path,
        output=output,
        model=model,
        stub=stub,
        dry_run=dry_run,
        max_blocks=max_blocks,
        batch_size=batch_size,
        min_chars=min_chars,
        labels_dump=labels_dump,
        labels_apply=labels_apply,
    )


def _do_pdf_highlight(
    *,
    pdf_path,
    output,
    model,
    stub,
    dry_run,
    max_blocks,
    batch_size,
    min_chars,
    labels_dump,
    labels_apply,
):
    from types import SimpleNamespace

    from .pdf_highlight._cli import run as _run

    ns = SimpleNamespace(
        pdf=Path(pdf_path),
        output=Path(output) if output else None,
        model=model,
        stub=stub,
        dry_run=dry_run,
        max_blocks=max_blocks,
        batch_size=batch_size,
        min_chars=min_chars,
        labels_dump=Path(labels_dump) if labels_dump else None,
        labels_apply=Path(labels_apply) if labels_apply else None,
    )
    sys.exit(_run(ns))


# ---------------------------------------------------------------------------
# Group: library
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def library() -> None:
    """Library-tree management."""


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
    from .cli._project_tree import link_project_tree

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
    from .cli._materialize import materialize

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
    from .cli._materialize import dematerialize

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
    from .storage import _library_index as idx

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
    from .storage import _library_index as idx

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
    from .storage import _library_index as idx

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
    from .storage import _library_index as idx

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
    from .storage._library_audit import audit, format_report

    report = audit(root)
    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2, default=str))
    else:
        click.echo(format_report(report))
    if strict and report.has_issues:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Group: mcp
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def mcp() -> None:
    """MCP (Model Context Protocol) server commands."""


@mcp.command("start")
@click.option("--dry-run", is_flag=True, help="Print launch plan without starting.")
@click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive.")
def mcp_start(dry_run, yes):
    """Start the scitex-scholar MCP server.

    \b
    Example:
      $ scitex-scholar mcp start
      $ scitex-scholar mcp start --dry-run
    """
    if dry_run:
        click.echo("DRY RUN — would start scitex-scholar MCP server (stdio transport)")
        return
    sys.exit(asyncio.run(_run_mcp_server_async()))


async def _run_mcp_server_async() -> int:
    import inspect

    from .mcp_server import main as mcp_main

    result: Any = mcp_main()
    if inspect.isawaitable(result):
        await result
    return 0


@mcp.command("list-tools")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def mcp_list_tools(as_json):
    """List available MCP tools.

    \b
    Example:
      $ scitex-scholar mcp list-tools
      $ scitex-scholar mcp list-tools --json
    """
    from ._mcp.all_handlers import __all__ as _handler_names

    tools = [
        "scholar_" + name.removesuffix("_handler") for name in sorted(_handler_names)
    ]
    if as_json:
        click.echo(_json.dumps({"tools": tools, "count": len(tools)}, indent=2))
        return
    for t in tools:
        click.echo(t)


@mcp.command("doctor")
def mcp_doctor():
    """Check MCP server dependencies.

    \b
    Example:
      $ scitex-scholar mcp doctor
    """
    click.echo("Checking MCP dependencies...")
    try:
        import fastmcp  # type: ignore

        click.secho(f"  OK  fastmcp {fastmcp.__version__}", fg="green")
    except ImportError:
        click.secho("  NG  fastmcp not installed", fg="red")
        click.echo("      Install: pip install scitex-scholar[mcp]")
        sys.exit(1)
    try:
        from ._mcp import all_handlers as _h

        click.secho(
            f"  OK  scitex-scholar handlers ({len(_h.__all__)} tools)", fg="green"
        )
    except Exception as exc:  # pragma: no cover
        click.secho(f"  NG  handler import error: {exc}", fg="red")
        sys.exit(1)
    click.echo("\nMCP server ready.")
    click.echo("Run: scitex-scholar mcp start")


@mcp.command("install")
@click.option("--claude-code", is_flag=True, help="Show Claude Code config snippet.")
@click.option("--dry-run", is_flag=True, help="Print plan without executing.")
@click.option("--yes", "-y", is_flag=True)
def mcp_install(claude_code, dry_run, yes):
    """Show MCP installation instructions.

    \b
    Example:
      $ scitex-scholar mcp install
      $ scitex-scholar mcp install --claude-code
    """
    if dry_run:
        click.echo(
            f"DRY RUN — would print install instructions (claude_code={claude_code})"
        )
        return
    if claude_code:
        click.echo("Add to Claude Code MCP config:")
        click.echo()
        click.echo('  "scitex-scholar": {')
        click.echo('    "command": "scitex-scholar",')
        click.echo('    "args": ["mcp", "start"]')
        click.echo("  }")
        return
    click.echo("scitex-scholar MCP Server Installation")
    click.echo("=" * 40)
    click.echo()
    click.echo("1. Install: pip install scitex-scholar[mcp]")
    click.echo("2. Config:  scitex-scholar mcp install --claude-code")
    click.echo("3. Test:    scitex-scholar mcp doctor")


# ---------------------------------------------------------------------------
# Group: skills
# ---------------------------------------------------------------------------


def _skills_dir() -> Path:
    return Path(__file__).parent / "_skills" / "scitex-scholar"


@cli.group(context_settings=CONTEXT_SETTINGS)
def skills() -> None:
    """Bundled skill leaves."""


@skills.command("list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def skills_list(as_json):
    """List bundled skill leaf names.

    \b
    Example:
      $ scitex-scholar skills list
    """
    d = _skills_dir()
    if not d.is_dir():
        if as_json:
            click.echo(_json.dumps([]))
        return
    names = sorted(p.stem for p in d.glob("*.md"))
    if as_json:
        click.echo(_json.dumps(names))
        return
    for n in names:
        click.echo(n)


@skills.command("get")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def skills_get(name, as_json):
    """Print the contents of a skill leaf.

    \b
    Example:
      $ scitex-scholar skills get 04_cli-reference
      $ scitex-scholar skills get 04_cli-reference --json
    """
    d = _skills_dir()
    p = d / f"{name}.md"
    if not p.exists():
        raise click.ClickException(f"Skill not found: {name} (looked in {d})")
    body = p.read_text()
    if as_json:
        click.echo(_json.dumps({"name": name, "path": str(p), "body": body}, indent=2))
    else:
        click.echo(body)


@skills.command("install")
@click.option(
    "--target",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Install dir (default: ~/.claude/skills/scitex-scholar).",
)
@click.option(
    "--symlink/--copy",
    default=True,
    help="Symlink (default) or copy the skills directory.",
)
@click.option("--force", is_flag=True, help="Replace existing target.")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def skills_install(target, symlink, force, dry_run, yes):
    """Install bundled skills to ~/.claude/skills/scitex-scholar/.

    \b
    Example:
      $ scitex-scholar skills install
      $ scitex-scholar skills install --copy --force
    """
    src = _skills_dir()
    dst = (
        Path(target) if target else Path("~/.claude/skills/scitex-scholar").expanduser()
    )
    if dry_run:
        click.echo(f"DRY RUN — would {'symlink' if symlink else 'copy'} {src} -> {dst}")
        return
    if not src.is_dir():
        raise click.ClickException(f"Skills source missing: {src}")
    if dst.exists() or dst.is_symlink():
        if not force:
            raise click.ClickException(f"{dst} exists; pass --force to replace")
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            import shutil

            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if symlink:
        dst.symlink_to(src.resolve())
    else:
        import shutil

        shutil.copytree(src, dst)
    click.echo(f"Installed skills -> {dst}")


# ---------------------------------------------------------------------------
# list-python-apis
# ---------------------------------------------------------------------------


@cli.command("list-python-apis", context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", count=True, help="-v: signatures.")
@click.option("--json", "as_json", is_flag=True)
def list_python_apis(verbose, as_json):
    """List public callables in scitex_scholar.__all__.

    \b
    Example:
      $ scitex-scholar list-python-apis
      $ scitex-scholar list-python-apis -v
    """
    import inspect

    import scitex_scholar as ss

    names = list(getattr(ss, "__all__", []))
    out: list[dict[str, str]] = []
    for n in names:
        if n.startswith("_") or n == "__version__":
            continue
        try:
            obj = getattr(ss, n)
        except Exception:
            obj = None
        sig = ""
        if verbose and callable(obj):
            try:
                sig = str(inspect.signature(obj))
            except (TypeError, ValueError):
                sig = ""
        out.append({"name": n, "signature": sig})

    if as_json:
        click.echo(_json.dumps(out, indent=2))
        return
    for entry in out:
        if verbose and entry["signature"]:
            click.echo(f"{entry['name']}{entry['signature']}")
        else:
            click.echo(entry["name"])


# ---------------------------------------------------------------------------
# Hidden deprecation aliases
# ---------------------------------------------------------------------------


@cli.command("single", hidden=True, context_settings=CONTEXT_SETTINGS)
@_paper_fetch_options
def alias_single(
    doi, title, project, browser_mode, chrome_profile, force, dry_run, yes, as_json
):
    """DEPRECATED: alias for `paper fetch`."""
    _warn_deprecated("single", "paper fetch")
    return _do_paper_fetch(
        doi=doi,
        title=title,
        project=project,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        force=force,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


@cli.command("parallel", hidden=True, context_settings=CONTEXT_SETTINGS)
@_paper_fetch_batch_options
def alias_parallel(
    dois,
    titles,
    project,
    num_workers,
    browser_mode,
    chrome_profile,
    dry_run,
    yes,
    as_json,
):
    """DEPRECATED: alias for `paper fetch-batch`."""
    _warn_deprecated("parallel", "paper fetch-batch")
    return _do_paper_fetch_batch(
        dois=list(dois),
        titles=list(titles),
        project=project,
        num_workers=num_workers,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


@cli.command("highlight", hidden=True, context_settings=CONTEXT_SETTINGS)
@_pdf_highlight_options
def alias_highlight(
    pdf_path,
    output,
    model,
    stub,
    dry_run,
    yes,
    max_blocks,
    batch_size,
    min_chars,
    labels_dump,
    labels_apply,
):
    """DEPRECATED: alias for `pdf highlight`."""
    _warn_deprecated("highlight", "pdf highlight")
    return _do_pdf_highlight(
        pdf_path=pdf_path,
        output=output,
        model=model,
        stub=stub,
        dry_run=dry_run,
        max_blocks=max_blocks,
        batch_size=batch_size,
        min_chars=min_chars,
        labels_dump=labels_dump,
        labels_apply=labels_apply,
    )


@cli.command("link-project-tree", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_link_options
def alias_link_project_tree(project_dir, force, dry_run, yes):
    """DEPRECATED: alias for `library link-project-tree`."""
    _warn_deprecated("link-project-tree", "library link-project-tree")
    return _do_link_project_tree(project_dir, force, dry_run, yes)


@cli.command("materialize", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_materialize_options
def alias_materialize(link_path, bib, dry_run, yes):
    """DEPRECATED: alias for `library materialize`."""
    _warn_deprecated("materialize", "library materialize")
    return _do_materialize(link_path, bib, dry_run, yes)


@cli.command("dematerialize", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_dematerialize_options
def alias_dematerialize(path, target, dry_run, yes):
    """DEPRECATED: alias for `library dematerialize`."""
    _warn_deprecated("dematerialize", "library dematerialize")
    return _do_dematerialize(path, target, dry_run, yes)


# Hidden top-level alias for the legacy `db <verb>` form. Mirrors `library db`.
@cli.group("db", hidden=True, context_settings=CONTEXT_SETTINGS)
def alias_db_group() -> None:
    """DEPRECATED: alias for `library db`."""


def _alias_db_warn() -> None:
    _warn_deprecated("db", "library db")


@alias_db_group.command("build")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--verbose", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def alias_db_build(ctx, library_root, verbose, dry_run, yes, as_json):
    _alias_db_warn()
    ctx.invoke(
        library_db_build,
        library_root=library_root,
        verbose=verbose,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


@alias_db_group.command("migrate")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
@click.pass_context
def alias_db_migrate(ctx, library_root, dry_run, yes):
    _alias_db_warn()
    ctx.invoke(library_db_migrate, library_root=library_root, dry_run=dry_run, yes=yes)


@alias_db_group.command("lookup")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--doi", default=None)
@click.option("--paper-id", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def alias_db_lookup(ctx, library_root, doi, paper_id, as_json):
    _alias_db_warn()
    ctx.invoke(
        library_db_lookup,
        library_root=library_root,
        doi=doi,
        paper_id=paper_id,
        as_json=as_json,
    )


@alias_db_group.command("list")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--limit", type=int, default=20)
@click.option("--offset", type=int, default=0)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def alias_db_list(ctx, library_root, limit, offset, as_json):
    _alias_db_warn()
    ctx.invoke(
        library_db_list,
        library_root=library_root,
        limit=limit,
        offset=offset,
        as_json=as_json,
    )


@alias_db_group.command("audit")
@click.option("--library-root", default=None, type=click.Path(path_type=Path))
@click.option("--json", "as_json", is_flag=True)
@click.option("--strict", is_flag=True)
@click.pass_context
def alias_db_audit(ctx, library_root, as_json, strict):
    _alias_db_warn()
    ctx.invoke(
        library_db_audit, library_root=library_root, as_json=as_json, strict=strict
    )


# ---------------------------------------------------------------------------
# Group: auth — institutional SSO session management
# ---------------------------------------------------------------------------


@cli.group(context_settings=CONTEXT_SETTINGS)
def auth() -> None:
    """Institutional SSO authentication (OpenAthens / EZProxy / Shibboleth).

    The cached session lives at
    `~/.scitex/scholar/cache/auth/<provider>.json`. It is refreshed
    lazily by `paper fetch`, but these commands let you inspect or
    drive the lifecycle directly — useful for debugging the SSO
    automator and pre-warming sessions for batch jobs.
    """


def _auth_cache_paths() -> list[Path]:
    """All cached auth session files."""
    home = Path.home() / ".scitex" / "scholar" / "cache" / "auth"
    if not home.exists():
        return []
    return sorted(p for p in home.glob("*.json") if p.is_file())


@auth.command("status", context_settings=CONTEXT_SETTINGS)
@click.option("--json", "as_json", is_flag=True)
def auth_status(as_json: bool) -> int:
    """Show cached SSO session state.

    \b
    Exit code:
      0  at least one session is valid
      1  no session, or all expired

    \b
    Example:
      $ scitex-scholar auth status
      $ scitex-scholar auth status --json
    """
    import datetime
    import json
    import time

    paths = _auth_cache_paths()
    rows: list[dict[str, Any]] = []
    any_valid = False
    for p in paths:
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            rows.append({"provider": p.stem, "status": "unreadable", "error": str(e)})
            continue
        # Try common expiry shapes: top-level "expires_at" / cookie list.
        expiry = data.get("expires_at") or data.get("expiry")
        cookie_count = len(data.get("cookies", []))
        if expiry is None and isinstance(data.get("cookies"), list):
            # Fall back: max cookie expiry.
            cookie_expiries = [
                c.get("expires", 0)
                for c in data["cookies"]
                if isinstance(c, dict) and c.get("expires")
            ]
            expiry = max(cookie_expiries) if cookie_expiries else None
        if expiry is None:
            status = "valid (unknown expiry)"
            any_valid = True
        elif float(expiry) > time.time():
            status = "valid"
            any_valid = True
        else:
            status = "expired"
        rows.append(
            {
                "provider": p.stem,
                "status": status,
                "cookies": cookie_count,
                "expires_at": (
                    datetime.datetime.fromtimestamp(float(expiry)).isoformat()
                    if expiry
                    else None
                ),
                "cache_path": str(p),
            }
        )

    if as_json:
        click.echo(json.dumps({"sessions": rows, "any_valid": any_valid}, indent=2))
    elif not rows:
        click.echo("No cached sessions found.")
    else:
        for r in rows:
            click.echo(
                f"{r['provider']:<15} {r['status']:<25} "
                f"cookies={r.get('cookies', '?')} expires={r.get('expires_at') or 'unknown'}"
            )

    return 0 if any_valid else 1


@auth.command("logout", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default=None, help="Specific provider (default: all).")
@click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive.")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted.")
def auth_logout(provider: str | None, yes: bool, dry_run: bool) -> int:
    """Clear cached SSO session(s) — forces next call to re-authenticate.

    \b
    Example:
      $ scitex-scholar auth logout
      $ scitex-scholar auth logout --provider openathens
      $ scitex-scholar auth logout --dry-run
    """
    paths = _auth_cache_paths()
    if provider:
        paths = [p for p in paths if p.stem == provider]
    if not paths:
        click.echo("No cached sessions to clear.")
        return 0
    click.echo(f"Will clear: {[str(p) for p in paths]}")
    if dry_run:
        return 0
    if not yes:
        click.echo(
            "Refusing to proceed without --yes/-y "
            "(mutating action; non-interactive by design).",
            err=True,
        )
        return 2
    cleared = 0
    for p in paths:
        try:
            p.unlink()
            cleared += 1
            click.echo(f"  cleared: {p}")
        except OSError as e:
            click.echo(f"  failed:  {p}: {e}", err=True)
    # Also clear sso_sessions/ directory if present.
    sso_dir = Path.home() / ".scitex" / "scholar" / "cache" / "auth" / "sso_sessions"
    if sso_dir.exists() and (provider is None or provider == "sso_sessions"):
        try:
            import shutil

            shutil.rmtree(sso_dir)
            click.echo(f"  cleared: {sso_dir}/")
        except OSError as e:
            click.echo(f"  failed:  {sso_dir}: {e}", err=True)
    click.echo(f"Cleared {cleared} session file(s).")
    return 0


@auth.command("login", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default="openathens", help="Provider to authenticate.")
@click.option(
    "--browser-mode",
    type=click.Choice(["stealth", "interactive"]),
    default="stealth",
)
def auth_login(provider: str, browser_mode: str) -> int:
    """Trigger SSO login flow now — pre-warm the cached session.

    \b
    Example:
      $ scitex-scholar auth login
      $ scitex-scholar auth login --browser-mode interactive
    """
    from scitex_scholar.auth import ScholarAuthManager

    async def _go() -> int:
        mgr = ScholarAuthManager()
        ok = await mgr.ensure_authenticate_async()
        return 0 if ok else 1

    return asyncio.run(_go())


@auth.command("refresh", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default=None, help="Specific provider (default: all).")
@click.pass_context
def auth_refresh(ctx: click.Context, provider: str | None) -> int:
    """Force re-login: equivalent to `auth logout --yes` followed by `auth login`."""
    rc = ctx.invoke(auth_logout, provider=provider, yes=True, dry_run=False)
    if rc != 0:
        return rc
    return ctx.invoke(
        auth_login, provider=provider or "openathens", browser_mode="stealth"
    )


# ---------------------------------------------------------------------------
# Shell completion (§1a)
# ---------------------------------------------------------------------------

try:
    from scitex_dev._cli._completion import attach_shell_completion

    attach_shell_completion(cli, prog_name="scitex-scholar")
except ImportError:
    pass


# Legacy: `bibtex --bibtex …` (no subcommand) form. Click can't easily
# disambiguate that within a group, so we pre-process argv in `main()`.
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _rewrite_argv_for_bibtex_alias(argv: list[str]) -> tuple[list[str], bool]:
    """Rewrite ``bibtex --bibtex …`` (no subcommand) → ``bibtex import --bibtex …``."""
    if len(argv) < 2 or argv[0] != "bibtex":
        return argv, False
    if argv[1] in {"import", "-h", "--help"}:
        return argv, False
    return ["bibtex", "import", *argv[1:]], True


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]

    bibtex_alias_used = False
    if raw and raw[0] == "bibtex":
        raw, bibtex_alias_used = _rewrite_argv_for_bibtex_alias(raw)

    if bibtex_alias_used:
        _warn_deprecated("bibtex --bibtex …", "bibtex import --bibtex …")

    try:
        cli.main(args=raw, prog_name="scitex-scholar", standalone_mode=False)
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Abort:
        click.secho("Aborted.", fg="red", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# EOF


# audit §4 — inject version into root --help
try:
    from importlib.metadata import version as _v

    cli.help = (
        f"scitex-scholar (v{_v('scitex-scholar')}) — " + (cli.help or "").lstrip()
    )
except Exception:
    pass
