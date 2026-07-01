#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: src/scitex_scholar/verify_cites/_cli.py
# ----------------------------------------
"""Click command for verify-cites.

Kept in its own module so it can be (a) run standalone via
``python -m scitex_scholar.verify_cites`` and (b) later attached to the main
``scitex-scholar`` group with ``cli.add_command(verify_cites_command)`` once
``_cli_main.py`` is split (it currently exceeds the repo line-limit gate, so we
do not edit it here).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ._core import compute_exit_code, verify_cites


@click.command("verify-cites")
@click.argument(
    "manuscript_dir",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--bib",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Override the .bib to check (else auto-resolved via the \\bibliography symlink chain).",
)
@click.option(
    "--out",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Sidecar path (default: <dir>/.scitex/scholar/citation_status.json).",
)
@click.option("--min-confidence", type=float, default=0.8, show_default=True)
@click.option(
    "--fail-on",
    default="stub,hallucinated,unlinked",
    show_default=True,
    help="Comma list of statuses that make the command fail-loud.",
)
@click.option("--offline", is_flag=True, help="Cache-only; do not hit the network.")
@click.option(
    "--emit-clew",
    is_flag=True,
    help="Push each verdict into clew via add_citation (no-op if clew absent).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the sidecar to stdout.")
def verify_cites_command(
    manuscript_dir, bib, out, min_confidence, fail_on, offline, emit_clew, as_json
):
    """Resolve every \\cite key to a real source and gate on the result.

    \b
    Example:
      $ python -m scitex_scholar.verify_cites paper/ --fail-on stub,hallucinated,unlinked
    """
    fail_set = [s.strip() for s in str(fail_on).split(",") if s.strip()]
    try:
        report = verify_cites(
            manuscript_dir,
            bib=bib,
            out=out,
            min_confidence=min_confidence,
            offline=offline,
        )
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc))

    if emit_clew:
        from ._core import push_to_clew

        pushed = push_to_clew(report)
        click.echo(f"clew: pushed {pushed} citation(s)")

    if as_json:
        click.echo(json.dumps(report.to_sidecar(), indent=2, ensure_ascii=False))
    else:
        click.echo(f"compiled bib: {report.bib_path}")
        summary = report.summary()
        click.echo("  ".join(f"{k}={v}" for k, v in sorted(summary.items())) or "no cites")
        for bad in ("hallucinated", "unverified", "stub"):
            keys = report.by_status(bad)
            if keys:
                click.echo(f"{bad.upper()}: {', '.join(keys)}")

    sys.exit(compute_exit_code(report, fail_set))


# EOF
