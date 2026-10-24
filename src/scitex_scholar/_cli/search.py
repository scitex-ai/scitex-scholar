#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/search.py

"""``search`` command for the Scholar CLI.

Thin adapter over :class:`ScholarSearchEngine.search` (the same CUI the
Django ``api/search`` view forwards to): query in, paper rows out. Human
output is one line per paper; ``--json`` emits the raw payload for pipes.

Registered by ``_cli_main`` as a top-level verb
(``cli.add_command(search)``): searching is a domain verb, not
self-maintenance plumbing (same rationale as ``list-python-apis``).
"""

from __future__ import annotations

import asyncio
import json as _json

import click

from ._scaffolding import CONTEXT_SETTINGS, spec_command_kwargs

_DEFAULT_MAX_RESULTS = 50
_MAX_RESULTS_CAP = 500


def _format_row(index: int, paper: dict) -> str:
    """One human line per paper: title, year, DOI handle."""
    title = paper.get("title") or "Untitled"
    year = paper.get("year") or ""
    doi = paper.get("doi") or ""
    head = f"{index + 1}. {title}"
    tail = " ".join(part for part in (f"({year})" if year else "", doi) if part)
    return f"{head} {tail}" if tail else head


@click.command(
    **spec_command_kwargs(
        "Search academic databases for papers.",
        examples=(
            ("{prog} search \"hippocampus -a Smith\"", "Keyword search."),
            ("{prog} search \"graph neural networks\" --max-results 20", "Fewer rows."),
            ("{prog} search \"year:2020-2024 epilepsy\" --json", "Machine-readable output."),
        ),
    ),
    context_settings=CONTEXT_SETTINGS,
)
@click.argument("query")
@click.option(
    "--max-results",
    type=click.IntRange(1, _MAX_RESULTS_CAP),
    default=_DEFAULT_MAX_RESULTS,
    show_default=True,
    help="Maximum papers to return (backend clamps 1-500).",
)
@click.option(
    "--mode",
    type=click.Choice(["parallel", "single"]),
    default="parallel",
    show_default=True,
    help="Search mode.",
)
@click.option("--dry-run", is_flag=True, help="Print plan without executing.")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def search(query, max_results, mode, dry_run, as_json):
    """Search academic databases for papers.

    \b
    Examples:
      $ scitex-scholar search "hippocampus -a Smith"
      $ scitex-scholar search "graph neural networks" --max-results 20 --json
    """
    if dry_run:
        click.echo(
            f"DRY RUN — would search {query!r} "
            f"(mode={mode}, max_results={max_results})"
        )
        return
    from scitex_scholar.search_engines.ScholarSearchEngine import ScholarSearchEngine

    engine = ScholarSearchEngine(default_mode=mode)
    payload = asyncio.run(engine.search(query, mode=mode, max_results=max_results))
    if as_json:
        click.echo(_json.dumps(payload, indent=2, default=str))
        return
    for index, paper in enumerate(payload.get("results", [])):
        click.echo(_format_row(index, paper if isinstance(paper, dict) else {}))
