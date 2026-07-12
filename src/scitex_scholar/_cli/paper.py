#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/paper.py

"""``paper`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.paper import paper`` +
``cli.add_command(paper)``. The private option-decorators / ``_do_*``
helpers are re-exported so the hidden top-level deprecation aliases
(``single``, ``parallel``) keep dispatching to a single implementation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS

# ---------------------------------------------------------------------------
# Group: paper
# ---------------------------------------------------------------------------


@click.group(context_settings=CONTEXT_SETTINGS)
def paper() -> None:
    """Operate on a paper / batch of papers."""


def _paper_fetch_options(f):
    f = click.option(
        "--doi",
        default=None,
        help="DOI of the paper. Accepts bare ('10.x/y'), 'doi:...', or "
        "'https://doi.org/...' / 'http://dx.doi.org/...' URLs.",
    )(f)
    f = click.option("--title", default=None, help="Paper title (resolves DOI).")(f)
    f = click.option(
        "--pdf-main",
        "--pdf",  # back-compat alias
        "pdf_path",
        default=None,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Local main PDF to import. Skips the browser stack; metadata "
        "enrichment still runs from --doi/--title.",
    )(f)
    f = click.option(
        "--pdf-supple",
        "pdf_supples",
        multiple=True,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Supplementary file (PDF/docx/xlsx). Repeatable. Stored as "
        "'supple-<original_name>' in the paper dir.",
    )(f)
    f = click.option(
        "--attachment",
        "attachments",
        multiple=True,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Anything else (data, code, slides). Repeatable. Stored as "
        "'additional-<original_name>' in the paper dir.",
    )(f)
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
    """Fetch a single paper into the library.

    \b
    Examples:
      $ scitex-scholar paper fetch --doi 10.1038/nature12373 --project demo
      $ scitex-scholar paper fetch --doi 10.1002/epi.70076 \\
            --pdf-main ~/Downloads/Liu_2026.pdf --project neurovista
      $ scitex-scholar paper fetch --doi 10.1038/s41467-020-15908-3 \\
            --pdf-supple ~/Downloads/41467_2020_15908_MOESM1_ESM.pdf \\
            --attachment ~/Downloads/dataset.csv --project neurovista
    """
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


def _do_paper_fetch(
    *,
    doi,
    title,
    pdf_path,
    pdf_supples=(),
    attachments=(),
    project,
    browser_mode,
    chrome_profile,
    force,
    dry_run,
    yes,
    as_json,
):
    # If --pdf-main is given without --doi/--title, try to extract DOI
    # from the PDF's first page.
    if pdf_path and not doi and not title:
        try:
            import re

            from pypdf import PdfReader

            text = PdfReader(str(pdf_path)).pages[0].extract_text() or ""
            m = re.search(r"10\.\d{4,}/\S+", text)
            if m:
                doi = m.group().rstrip(".,;)")
                click.echo(f"Extracted DOI from PDF: {doi}")
        except Exception as exc:
            click.secho(
                f"Could not auto-extract DOI from {pdf_path}: {exc}",
                fg="yellow",
            )

    if not doi and not title:
        raise click.UsageError(
            "Provide --doi, --title, or --pdf-main (with extractable DOI)."
        )
    if dry_run:
        click.echo(
            f"DRY RUN — would fetch (doi={doi!r}, title={title!r}, "
            f"pdf_main={pdf_path!r}, supples={list(pdf_supples)!r}, "
            f"attachments={list(attachments)!r}, "
            f"project={project!r}, browser_mode={browser_mode!r})"
        )
        return 0
    rc = asyncio.run(
        _run_paper_fetch_async(
            doi=doi,
            title=title,
            pdf_path=pdf_path,
            pdf_supples=list(pdf_supples or ()),
            attachments=list(attachments or ()),
            project=project,
            browser_mode=browser_mode,
            chrome_profile=chrome_profile,
            force=force,
        )
    )
    sys.exit(rc)


async def _run_paper_fetch_async(
    *,
    doi,
    title,
    pdf_path,
    pdf_supples,
    attachments,
    project,
    browser_mode,
    chrome_profile,
    force,
) -> int:
    from ..pipelines.ScholarPipelineSingle import ScholarPipelineSingle

    doi_or_title = doi or title
    pipeline = ScholarPipelineSingle(
        browser_mode=browser_mode,
        chrome_profile=chrome_profile,
    )
    await pipeline.process_single_paper(
        doi_or_title=doi_or_title,
        project=project,
        force=force,
        pdf_path=str(pdf_path) if pdf_path else None,
        pdf_supples=[str(p) for p in pdf_supples] if pdf_supples else None,
        attachments=[str(p) for p in attachments] if attachments else None,
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
    from ..pipelines.ScholarPipelineParallel import ScholarPipelineParallel

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


# EOF
