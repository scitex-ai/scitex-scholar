#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/pdf.py

"""``pdf`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.pdf import pdf`` +
``cli.add_command(pdf)``. The private option-decorator / ``_do_*`` helper
are re-exported so the hidden top-level deprecation alias (``highlight``)
keeps dispatching to a single implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS, _INT_OR_HELP

# ---------------------------------------------------------------------------
# Group: pdf
# ---------------------------------------------------------------------------


@click.group(context_settings=CONTEXT_SETTINGS)
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

    from ..pdf_highlight._cli import run as _run

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


# EOF
