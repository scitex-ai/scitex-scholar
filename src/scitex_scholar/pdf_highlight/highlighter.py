"""Thin orchestrator — wires extraction, classification, and annotation.

Public entry points:
- :func:`highlight_pdf` — end-to-end: extract → classify → write annotated PDF.
- :func:`save_with_highlights` — apply pre-classified labels to a document.
- :func:`apply_classifications` — merge offline JSON labels into blocks.

The source PDF bytes are not modified; highlights are PDF annotation
objects compatible with any PDF viewer.
"""

from __future__ import annotations

import datetime as _dt
import importlib.metadata as _md
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pymupdf

from ._annotator import add_legend_page, apply_highlights
from ._blocks import Block, extract_blocks
from ._classifier import API_KEY_ENV, classify_llm, classify_stub
from ._colors import CATEGORIES, CATEGORY_LABELS, COLOR_RGB

__all__ = [
    "CATEGORIES",
    "COLOR_RGB",
    "CATEGORY_LABELS",
    "Block",
    "HighlightResult",
    "apply_classifications",
    "extract_blocks",
    "highlight_pdf",
    "save_with_highlights",
]


def _package_version() -> str:
    try:
        return _md.version("scitex-scholar")
    except Exception:
        return "unknown"


def _default_signature(model: Optional[str]) -> str:
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"Highlighted by scitex-scholar v{_package_version()} (pdf_highlight) — {ts}"


def apply_classifications(
    blocks: list[Block],
    classifications: list[dict[str, Any]],
) -> int:
    """Assign offline-produced labels to already-extracted blocks.

    Each entry must contain at least ``id`` and ``category``; ``confidence``
    is optional (defaults to 0.0). Categories outside :data:`CATEGORIES`
    are silently dropped.

    Returns the number of blocks that received a label.
    """
    by_id = {b.id: b for b in blocks}
    n = 0
    for item in classifications:
        b = by_id.get(int(item["id"]))
        if b is None:
            continue
        cat = item.get("category", "none")
        if cat not in CATEGORIES:
            continue
        b.category = cat
        b.confidence = float(item.get("confidence", 0.0))
        n += 1
    return n


def save_with_highlights(
    doc: pymupdf.Document,
    blocks: list[Block],
    output_path: str | os.PathLike,
    *,
    add_legend: bool = True,
    signature: Optional[str] = None,
    model_label: Optional[str] = None,
    source_name: Optional[str] = None,
    min_confidence: float = 0.0,
    on_info: Optional[Any] = None,
) -> int:
    """Write ``doc`` with highlight annotations for all labelled blocks.

    When ``add_legend=True`` (default) a colour legend + signature page is
    prepended so readers can see which colour means what. ``min_confidence``
    suppresses highlights below that confidence.

    ``on_info`` (optional callable) receives progress messages.

    The save deliberately uses ``garbage=0, deflate=False``. The earlier
    ``garbage=3, deflate=True`` recompressed every stream of the source
    PDF, which on a large (20 MB+) image-heavy paper ran for minutes
    entirely inside pymupdf's C code — and because CPython only delivers
    ``KeyboardInterrupt`` between bytecode ops, that made the run both
    slow *and* uninterruptible (Ctrl-C queued but never fired). Appending
    the annotation objects without recompression is near-instant and keeps
    the C calls short enough to stay responsive to signals.

    Returns the number of highlight annotations added (not counting the
    legend page).
    """
    info = on_info or (lambda _msg: None)
    n = apply_highlights(doc, blocks, min_confidence=min_confidence, on_info=on_info)
    if add_legend:
        add_legend_page(
            doc,
            signature=signature or _default_signature(model_label),
            model_label=model_label,
            source_name=source_name or "(unknown)",
        )
    out = Path(output_path)
    info(f"      writing {doc.page_count} pages → {out}")
    doc.save(out, garbage=0, deflate=False)
    size_mb = out.stat().st_size / 1e6
    info(f"      wrote {size_mb:.1f} MB")
    return n


@dataclass
class HighlightResult:
    input_path: Path
    output_path: Optional[Path]
    blocks: list[Block]
    pages: int
    annotations_added: int

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for b in self.blocks:
            c[b.category or "none"] = c.get(b.category or "none", 0) + 1
        return c


def highlight_pdf(
    pdf_path: str | os.PathLike,
    output_path: Optional[str | os.PathLike] = None,
    *,
    model: str = "claude-haiku-4-5-20251001",
    use_stub: bool = False,
    dry_run: bool = False,
    max_blocks: int = 0,
    batch_size: int = 25,
    min_chars: int = 40,
    sentence_level: bool = True,
    add_legend: bool = True,
    min_confidence: float = 0.0,
    concurrency: int = 4,
    on_info: Optional[Any] = None,
    on_warning: Optional[Any] = None,
) -> HighlightResult:
    """Annotate a PDF with rhetorical-role highlights.

    Args:
        pdf_path: Input PDF path.
        output_path: Output PDF. Defaults to ``<input>.highlighted.pdf``.
        model: Anthropic model ID used by the LLM classifier.
        use_stub: If True, classify with a keyword heuristic (no API call).
        dry_run: If True, classify but do not write the output PDF.
        max_blocks: If >0, truncate to the first N extracted units.
        batch_size: Classifier batch size (units per API call).
        min_chars: Minimum text length for an extracted unit.
        sentence_level: If True (default), classify and highlight at
            sentence granularity. If False, use paragraph-level (less
            precise but ~5× cheaper on long papers).
        add_legend: If True, prepend a colour legend + signature page.

    Returns:
        ``HighlightResult`` with the classified units and annotation count.
    """
    info = on_info or (lambda _msg: None)
    warn = on_warning or (lambda _msg: None)

    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(pdf)

    out: Optional[Path]
    if dry_run:
        out = None
    else:
        out = (
            Path(output_path)
            if output_path
            else pdf.with_name(pdf.stem + ".highlighted.pdf")
        )

    info(
        f"[1/3] Extracting {'sentences' if sentence_level else 'paragraphs'} from {pdf}"
    )
    doc, blocks = extract_blocks(
        pdf, min_chars=min_chars, sentence_level=sentence_level
    )
    if max_blocks > 0:
        blocks = blocks[:max_blocks]
    info(f"      {len(blocks)} candidate units across {doc.page_count} pages")

    info(f"[2/3] Classifying ({'stub' if use_stub else model})")
    if use_stub:
        classify_stub(blocks)
    else:
        if not os.environ.get(API_KEY_ENV):
            raise RuntimeError(
                f"{API_KEY_ENV} is not set (or call with use_stub=True). "
                "Scholar uses a namespaced key and does not read the ambient "
                "ANTHROPIC_API_KEY."
            )
        classify_llm(
            blocks,
            model=model,
            batch_size=batch_size,
            concurrency=concurrency,
            on_warning=warn,
            on_info=info,
        )

    added = 0
    if dry_run:
        info("[3/3] dry-run — not writing PDF")
    else:
        assert out is not None
        info(f"[3/3] Writing highlights to {out}")
        added = save_with_highlights(
            doc,
            blocks,
            out,
            add_legend=add_legend,
            model_label=(None if use_stub else model),
            source_name=pdf.name,
            min_confidence=min_confidence,
            on_info=info,
        )
        info(f"      added {added} highlight annotations")

    return HighlightResult(
        input_path=pdf,
        output_path=out,
        blocks=blocks,
        pages=doc.page_count,
        annotations_added=added,
    )
