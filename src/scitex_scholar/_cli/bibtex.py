#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/bibtex.py

"""``bibtex`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.bibtex import bibtex`` +
``cli.add_command(bibtex)``. The private option-decorator / ``_do_*``
helper are re-exported for consistency with the other extracted groups
(and for the legacy ``bibtex --bibtex ...`` argv-rewrite in ``main()``,
which re-dispatches through the normal ``bibtex import`` command).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS

# ---------------------------------------------------------------------------
# Group: bibtex
# ---------------------------------------------------------------------------


@click.group(context_settings=CONTEXT_SETTINGS)
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
    from ..pipelines.ScholarPipelineBibTeX import ScholarPipelineBibTeX

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


# EOF
