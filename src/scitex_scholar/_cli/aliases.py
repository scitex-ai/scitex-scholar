#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/aliases.py

"""Hidden pre-1.3.0 deprecation aliases for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.aliases import (...)`` +
one ``cli.add_command(...)`` per alias. Each alias just re-dispatches to
the canonical implementation living in ``.paper`` / ``.pdf`` / ``.library``.
"""

from __future__ import annotations

from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS, _warn_deprecated
from .library import (
    _do_dematerialize,
    _do_link_project_tree,
    _do_materialize,
    _library_dematerialize_options,
    _library_link_options,
    _library_materialize_options,
    library_db_audit,
    library_db_build,
    library_db_list,
    library_db_lookup,
    library_db_migrate,
)
from .paper import (
    _do_paper_fetch,
    _do_paper_fetch_batch,
    _paper_fetch_batch_options,
    _paper_fetch_options,
)
from .pdf import _do_pdf_highlight, _pdf_highlight_options

# ---------------------------------------------------------------------------
# Hidden deprecation aliases
# ---------------------------------------------------------------------------


@click.command("single", hidden=True, context_settings=CONTEXT_SETTINGS)
@_paper_fetch_options
def alias_single(
    doi,
    title,
    pdf_path,
    pdf_supples,
    attachments,
    project,
    browser_mode,
    chrome_profile,
    force,
    dry_run,
    yes,
    as_json,
):
    """DEPRECATED: alias for `paper fetch`."""
    _warn_deprecated("single", "paper fetch")
    return _do_paper_fetch(
        doi=doi,
        title=title,
        pdf_path=pdf_path,
        pdf_supples=list(pdf_supples or ()),
        attachments=list(attachments or ()),
        project=project,
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
        force=force,
        dry_run=dry_run,
        yes=yes,
        as_json=as_json,
    )


@click.command("parallel", hidden=True, context_settings=CONTEXT_SETTINGS)
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


@click.command("highlight", hidden=True, context_settings=CONTEXT_SETTINGS)
@_pdf_highlight_options
def alias_highlight(
    pdf_paths,
    output,
    model,
    stub,
    dry_run,
    yes,
    max_blocks,
    batch_size,
    min_chars,
    min_confidence,
    concurrency,
    labels_dump,
    labels_apply,
):
    """DEPRECATED: alias for `pdf highlight`."""
    _warn_deprecated("highlight", "pdf highlight")
    return _do_pdf_highlight(
        pdf_paths=pdf_paths,
        output=output,
        model=model,
        stub=stub,
        dry_run=dry_run,
        max_blocks=max_blocks,
        batch_size=batch_size,
        min_chars=min_chars,
        min_confidence=min_confidence,
        concurrency=concurrency,
        labels_dump=labels_dump,
        labels_apply=labels_apply,
    )


@click.command("link-project-tree", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_link_options
def alias_link_project_tree(project_dir, force, dry_run, yes):
    """DEPRECATED: alias for `library link-project-tree`."""
    _warn_deprecated("link-project-tree", "library link-project-tree")
    return _do_link_project_tree(project_dir, force, dry_run, yes)


@click.command("materialize", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_materialize_options
def alias_materialize(link_path, bib, dry_run, yes):
    """DEPRECATED: alias for `library materialize`."""
    _warn_deprecated("materialize", "library materialize")
    return _do_materialize(link_path, bib, dry_run, yes)


@click.command("dematerialize", hidden=True, context_settings=CONTEXT_SETTINGS)
@_library_dematerialize_options
def alias_dematerialize(path, target, dry_run, yes):
    """DEPRECATED: alias for `library dematerialize`."""
    _warn_deprecated("dematerialize", "library dematerialize")
    return _do_dematerialize(path, target, dry_run, yes)


# Hidden top-level alias for the legacy `db <verb>` form. Mirrors `library db`.
@click.group("db", hidden=True, context_settings=CONTEXT_SETTINGS)
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


# EOF
