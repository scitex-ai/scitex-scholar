"""CLI entry point for the semantic PDF highlighter.

Invoked as:

    python -m scitex_scholar.pdf_highlight PDF [options]
    scitex-scholar highlight PDF [options]   # once wired into __main__.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scitex_logging import getLogger

from .highlighter import (
    CATEGORIES,
    apply_classifications,
    extract_blocks,
    highlight_pdf,
    save_with_highlights,
)

logger = getLogger(__name__)


def build_parser(
    parser: argparse.ArgumentParser | None = None,
) -> argparse.ArgumentParser:
    p = parser or argparse.ArgumentParser(
        prog="scitex-scholar-highlight",
        description="Overlay semantic highlights on a PDF (in-place classification via Claude).",
    )
    p.add_argument("pdf", type=Path, help="Input PDF path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PDF (default: <input>.highlighted.pdf)",
    )
    p.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Anthropic model ID (default: %(default)s)",
    )
    p.add_argument(
        "--stub",
        action="store_true",
        help="Use offline keyword heuristic (no API calls)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify and print summary; do not write output",
    )
    p.add_argument(
        "--max-blocks",
        type=int,
        default=0,
        help="Truncate to first N blocks (smoke testing)",
    )
    p.add_argument("--batch-size", type=int, default=25)
    p.add_argument("--min-chars", type=int, default=40)
    p.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Skip highlights below this model confidence (0-1). "
        "Try 0.85 to keep only high-certainty highlights.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of classification batches sent in parallel (default: 4).",
    )

    # Offline label workflow
    p.add_argument(
        "--labels-dump",
        type=Path,
        default=None,
        help="Extract blocks to JSON at this path and exit (id, page, text)",
    )
    p.add_argument(
        "--labels-apply",
        type=Path,
        default=None,
        help="Apply labels from JSON (list of {id, category, confidence}); no LLM call",
    )
    return p


def _dump_blocks(pdf: Path, out_json: Path, min_chars: int) -> int:
    doc, blocks = extract_blocks(pdf, min_chars=min_chars)
    data = [{"id": b.id, "page": b.page, "text": b.text} for b in blocks]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    logger.info(f"dumped {len(data)} blocks ({doc.page_count} pages) -> {out_json}")
    return 0


def _apply_labels(pdf: Path, labels_json: Path, output: Path | None) -> int:
    doc, blocks = extract_blocks(pdf)
    labels = json.loads(labels_json.read_text())
    n_labelled = apply_classifications(blocks, labels)
    out = output or pdf.with_name(pdf.stem + ".highlighted.pdf")
    n_annot = save_with_highlights(doc, blocks, out, on_info=logger.info)
    logger.success(f"applied {n_labelled} labels, wrote {n_annot} highlights -> {out}")
    return 0


def run(args: argparse.Namespace) -> int:
    """Execute the highlight pipeline with a pre-parsed Namespace.

    This is the integration point used by the top-level ``scitex-scholar
    highlight`` subcommand. It accepts whatever ``build_parser`` produces
    regardless of where that parser was constructed.
    """
    if args.labels_dump and args.labels_apply:
        logger.error("--labels-dump and --labels-apply are mutually exclusive")
        return 2

    if args.labels_dump:
        return _dump_blocks(args.pdf, args.labels_dump, args.min_chars)

    if args.labels_apply:
        return _apply_labels(args.pdf, args.labels_apply, args.output)

    # Fail fast, fail loud: a missing file or unset API key is a hard error
    # the operator must see. We log .fail (with the exception type) and
    # return non-zero rather than swallowing the cause behind a terse line.
    try:
        result = highlight_pdf(
            args.pdf,
            output_path=args.output,
            model=args.model,
            use_stub=args.stub,
            dry_run=args.dry_run,
            max_blocks=args.max_blocks,
            batch_size=args.batch_size,
            min_chars=args.min_chars,
            min_confidence=getattr(args, "min_confidence", 0.0),
            concurrency=getattr(args, "concurrency", 4),
            on_info=logger.info,
            on_warning=logger.warning,
        )
    except FileNotFoundError as exc:
        logger.fail(f"input PDF not found: {exc}")
        return 2
    except RuntimeError as exc:
        logger.fail(str(exc))
        return 2

    counts = result.counts()
    for cat in (*CATEGORIES, "none"):
        if counts.get(cat):
            logger.info(f"  {cat:<22} {counts[cat]:>3}")
    if result.output_path:
        logger.success(
            f"wrote {result.annotations_added} highlights to {result.output_path}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
