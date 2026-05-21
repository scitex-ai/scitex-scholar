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
    from types import SimpleNamespace

    from scitex_logging import getLogger

    from .pdf_highlight._cli import run as _run

    logger = getLogger(__name__)

    # Skip already-highlighted outputs and de-dup (a glob commonly catches
    # both a file and the symlink pointing at it).
    seen: set[Path] = set()
    targets: list[Path] = []
    for p in pdf_paths:
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
# Group: library
# ---------------------------------------------------------------------------


class _LibraryGroup(_CategorizedGroup):
    SECTIONS = [
        ("Daily", ["list", "open-urls", "refresh"]),
        ("Layout", ["bind", "link-project-tree", "materialize", "dematerialize"]),
        ("Share", ["sync", "export", "zotero"]),
        ("Database", ["db", "audit-files"]),
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


@cli.group(cls=_LibraryGroup, context_settings=CONTEXT_SETTINGS)
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
@click.option("--dry-run", is_flag=True)
@click.option(
    "--db", default=None, help="Path to zotero.sqlite (auto-detect if omitted)."
)
def library_zotero_import(
    project, collection, tags, match_all, include_pdfs, limit, dry_run, db
):
    """Import from local Zotero database into the Scholar library."""
    if not project:
        raise click.UsageError("--project is required for Zotero import.")
    from .integration.zotero import ZoteroLocalMigrator

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
def library_zotero_export(project, output_dir, include_pdfs):
    """Export Scholar papers as a Zotero-importable package (BibTeX + PDFs)."""
    if not project:
        raise click.UsageError("--project is required for Zotero export.")
    from .integration.zotero import ZoteroLocalMigrator

    mig = ZoteroLocalMigrator(project=project)

    if output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = (
            _default_library_root().parent / "exports" / f"zotero-{project}-{ts}"
        )
    output_dir = Path(output_dir)
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
    """Compare Zotero vs Scholar — show items present in one but not the other."""
    if not project:
        raise click.UsageError("--project is required.")
    from .integration.zotero import ZoteroLocalMigrator

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
    from .storage._project_reconcile import reconcile_projects

    rec = reconcile_projects(root, dry_run=dry_run)

    # 2) Refresh symlinks: walk MASTER, call canonical update_symlink per
    #    (paper, project) pair. Limit to PROJECT if given.
    from .config import ScholarConfig
    from .storage._LibraryManager import LibraryManager

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
def library_export(project, fmt, output, library_root, dry_run):
    """Export PROJECT in a portable format.

    \b
    Default location:
      <project-dir>/.scitex/scholar/exports/<project>-<ts>.<ext>  (when bound)
      ~/.scitex/scholar/exports/<project>-<ts>.<ext>              (otherwise)

    \b
    Examples:
      $ scitex-scholar library export neurovista
      $ scitex-scholar library export neurovista --format bibtex
      $ scitex-scholar library export neurovista --format flat-pdfs -o /tmp/x.tar.gz
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
        if not yes and not click.confirm("Proceed?", default=True):
            return
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
    if not yes and not click.confirm("Proceed?", default=True):
        return
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
def library_sync(host, project, pull, delete, dry_run, copy_links, remote_path):
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
        from .cli._url_utils import get_best_url

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
        from .cli.open_browser_monitored import open_browser_with_monitoring
        from .config import ScholarConfig

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

    from .cli.open_browser import open_browser_with_urls

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

    from .cli._url_utils import get_best_url

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
