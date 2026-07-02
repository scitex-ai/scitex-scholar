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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click


# TODO(scitex-dev): import scitex_dev.click_helpers.CategorizedGroup once
# available; currently scitex-dev does not export it, so we fall back to
# plain click.Group.
class _CategorizedGroup(click.Group):
    """Click Group that renders ``--help`` commands grouped by section.

    Subclass and set ``SECTIONS`` to ``[("Section name", ["cmd1", ...]), ...]``.
    Commands not listed in any section land under ``[Other]``.
    """

    SECTIONS: list = []

    def format_commands(self, ctx, formatter):
        commands = {
            n: c for n, c in self.commands.items() if not getattr(c, "hidden", False)
        }
        seen: set = set()
        with formatter.section("Commands"):
            for label, names in self.SECTIONS:
                rows = []
                for name in names:
                    cmd = commands.get(name)
                    if cmd is None:
                        continue
                    rows.append((name, cmd.get_short_help_str()))
                    seen.add(name)
                if rows:
                    formatter.write(f"\n  [{label}]\n")
                    for n, s in rows:
                        formatter.write(f"    {n:<26}{s}\n")
            other = sorted(n for n in commands if n not in seen)
            if other:
                formatter.write("\n  [Other]\n")
                for n in other:
                    formatter.write(f"    {n:<26}{commands[n].get_short_help_str()}\n")


# Top-level cli: same renderer with workflow/dev split. Replaces the
# unused scitex-dev `CategorizedGroup` import that fell back to plain
# click.Group when scitex-dev didn't actually export it.
class _RootGroup(_CategorizedGroup):
    SECTIONS = [
        ("Workflow", ["paper", "bibtex", "pdf", "library", "auth"]),
        (
            "Dev",
            [
                "list-python-apis",
                "mcp",
                "skills",
                "install-shell-completion",
                "print-shell-completion",
            ],
        ),
    ]


CategorizedGroup = _RootGroup  # used by @click.group(cls=...)


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class _IntOrHelp(click.ParamType):
    """An integer option type that treats ``-h``/``--help`` as a help request.

    Click consumes the token after a value-taking option as that option's
    value, so ``--batch-size -h`` would otherwise fail with "not a valid
    integer". Here we detect a help token and print the command help instead.
    """

    name = "integer"

    def convert(self, value, param, ctx):
        if isinstance(value, str) and value in ("-h", "--help"):
            click.echo(ctx.get_help())
            ctx.exit()
        try:
            return int(value)
        except (TypeError, ValueError):
            self.fail(f"{value!r} is not a valid integer", param, ctx)


_INT_OR_HELP = _IntOrHelp()

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
    f = click.argument(
        "pdf_paths",
        nargs=-1,
        required=True,
        type=click.Path(dir_okay=False, path_type=Path),
    )(f)
    f = click.option(
        "-o",
        "--output",
        default=None,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Output PDF (default: <input>.highlighted.pdf).",
    )(f)
    f = click.option(
        "--model",
        default="claude-haiku-4-5-20251001",
        show_default=True,
        help="Anthropic model ID for classification. An unknown ID lists the "
        "available models.",
    )(f)
    f = click.option(
        "--stub", is_flag=True, help="Use offline keyword heuristic (no API calls)."
    )(f)
    f = click.option(
        "--dry-run", is_flag=True, help="Classify and print summary; do not write."
    )(f)
    f = click.option(
        "--yes",
        "-y",
        is_flag=True,
        help="Assume yes to prompts; do not ask for confirmation.",
    )(f)
    f = click.option(
        "--max-blocks",
        type=_INT_OR_HELP,
        default=0,
        show_default=True,
        help="Classify only the first N text blocks (0 = all). For smoke tests.",
    )(f)
    f = click.option(
        "--batch-size",
        type=_INT_OR_HELP,
        default=25,
        show_default=True,
        help="Number of text blocks sent to the model per API request.",
    )(f)
    f = click.option(
        "--min-chars",
        type=_INT_OR_HELP,
        default=40,
        show_default=True,
        help="Skip text blocks shorter than this many characters.",
    )(f)
    f = click.option(
        "--min-confidence",
        type=float,
        default=0.0,
        show_default=True,
        help="Skip highlights below this model confidence (0-1). "
        "Try 0.85 to keep only high-certainty highlights.",
    )(f)
    f = click.option(
        "--concurrency",
        type=_INT_OR_HELP,
        default=4,
        show_default=True,
        help="Classification batches sent to the model in parallel.",
    )(f)
    f = click.option(
        "--labels-dump",
        default=None,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Write extracted blocks to this JSON file and exit (no API calls).",
    )(f)
    f = click.option(
        "--labels-apply",
        default=None,
        type=click.Path(dir_okay=False, path_type=Path),
        help="Apply pre-computed labels from this JSON file (no API calls).",
    )(f)
    return f


@pdf.command("highlight")
@_pdf_highlight_options
def pdf_highlight(
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
    """Overlay semantic highlights on one or more PDFs.

    Accepts multiple paths (e.g. a shell glob), so ``*.pdf`` highlights a
    whole directory in one invocation. Already-highlighted outputs
    (``*.highlighted.pdf``) are skipped automatically.

    \b
    Example:
      $ scitex-scholar pdf highlight paper.pdf --stub
      $ scitex-scholar pdf highlight refs/*.pdf
    """
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


def _do_pdf_highlight(
    *,
    pdf_paths,
    output,
    model,
    stub,
    dry_run,
    max_blocks,
    batch_size,
    min_chars,
    min_confidence,
    concurrency,
    labels_dump,
    labels_apply,
):
    import glob as _glob
    from types import SimpleNamespace

    from scitex_logging import getLogger

    from .pdf_highlight._cli import run as _run

    logger = getLogger(__name__)

    # Expand glob patterns ourselves. The shell normally expands `*.pdf`
    # before we see it, but not always: a quoted pattern, a no-match
    # passthrough, or a non-expanding caller (Windows tools, some IDEs)
    # hands us a literal `*.pdf`. Treat any arg containing glob
    # metacharacters that is not itself an existing file as a pattern.
    expanded: list[str] = []
    for p in pdf_paths:
        s = str(p)
        if any(ch in s for ch in "*?[") and not Path(s).exists():
            matches = sorted(_glob.glob(s))
            if not matches:
                logger.fail(f"glob matched no files: {s}")
                sys.exit(2)
            expanded.extend(matches)
        else:
            expanded.append(s)

    # Skip already-highlighted outputs and de-dup (a glob commonly catches
    # both a file and the symlink pointing at it).
    seen: set[Path] = set()
    targets: list[Path] = []
    for p in expanded:
        rp = Path(p).resolve()
        if rp.name.endswith(".highlighted.pdf"):
            logger.info(f"skipping already-highlighted file: {p}")
            continue
        if rp in seen:
            continue
        seen.add(rp)
        targets.append(Path(p))

    if not targets:
        logger.fail("no PDFs to highlight after filtering")
        sys.exit(2)

    # Single-input-only flags are ambiguous across a batch — fail loud
    # rather than silently applying one output path to many inputs.
    if len(targets) > 1:
        for flag, val in (
            ("--output", output),
            ("--labels-dump", labels_dump),
            ("--labels-apply", labels_apply),
        ):
            if val:
                logger.fail(f"{flag} cannot be used with multiple input PDFs")
                sys.exit(2)

    multi = len(targets) > 1
    rc = 0
    for idx, pdf_path in enumerate(targets, start=1):
        if multi:
            logger.info(f"=== [{idx}/{len(targets)}] {pdf_path} ===")
        ns = SimpleNamespace(
            pdf=Path(pdf_path),
            output=Path(output) if output else None,
            model=model,
            stub=stub,
            dry_run=dry_run,
            max_blocks=max_blocks,
            batch_size=batch_size,
            min_chars=min_chars,
            min_confidence=min_confidence,
            concurrency=concurrency,
            labels_dump=Path(labels_dump) if labels_dump else None,
            labels_apply=Path(labels_apply) if labels_apply else None,
        )
        rc = _run(ns) or rc
    sys.exit(rc)


# ---------------------------------------------------------------------------
# Group: library  (extracted -> ._cli.library; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.library import (  # noqa: E402  (after `cli` is defined above)
    _do_dematerialize,
    _do_link_project_tree,
    _do_materialize,
    _library_dematerialize_options,
    _library_link_options,
    _library_materialize_options,
    library,
    library_db_audit,
    library_db_build,
    library_db_list,
    library_db_lookup,
    library_db_migrate,
)

cli.add_command(library)


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
    from scitex_scholar.config import ScholarConfig

    auth_dir = ScholarConfig().path_manager.get_cache_auth_dir()
    if not auth_dir.exists():
        return []
    return sorted(p for p in auth_dir.glob("*.json") if p.is_file())


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
    from scitex_scholar.config import ScholarConfig

    sso_dir = ScholarConfig().path_manager.get_cache_auth_dir() / "sso_sessions"
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
    """Force re-login: equivalent to `auth logout --yes` followed by `auth login`.

    \b
    Examples:
      $ scitex-scholar auth refresh
      $ scitex-scholar auth refresh --provider openathens
    """
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
