---
description: |
  [TOPIC] Semantic Highlight
  [DETAILS] Overlay rhetorical-role highlights (claim/method/limitation/supportive/contradictive) onto a PDF via Claude. 5-colour scheme, sentence-level granularity, legend page appended.
tags: [scitex-scholar-semantic-highlight, scitex-scholar]
---


# Semantic PDF highlighting

Annotate a paper with colour-coded highlights that separate **what the paper claims** from method descriptions, self-admitted limitations, and stance toward related work. The original PDF bytes are not modified — highlights are standard PDF annotation objects (any viewer shows them, any viewer can strip them).

## Categories & colours

| colour | category | meaning |
|---|---|---|
| green  | `focal_claim`            | what the paper clarifies, suggests, demonstrates, establishes |
| purple | `focal_method`           | novel method, model, cohort, or analysis unique to the paper |
| red    | `focal_limitation`       | self-admitted caveat, confound, or threat to validity |
| blue   | `related_supportive`     | prior work whose finding supports this paper's position |
| orange | `related_contradictive`  | prior work whose finding contradicts this paper |

Precision-biased: when uncertain, the classifier returns `none` and no highlight is drawn. Sentence-level granularity by default — a paragraph is not painted whole just because one of its sentences is a claim.

## Pipeline

```
PDF
  → PyMuPDF block extraction (paragraph bboxes)
  → sentence splitting inside each block (abbreviation-aware)
  → Claude classifier (5 categories, batched, JSON-structured output)
  → tight per-line quads via PyMuPDF dict layout
  → PDF Highlight annotations (opacity 0.4) + prepended legend page
  → save
```

## CLI

```bash
# Via the top-level entrypoint
scitex-scholar highlight /path/to/paper.pdf

# Options
scitex-scholar highlight paper.pdf \
    --output paper.highlighted.pdf \
    --model claude-haiku-4-5-20251001   # default; use sonnet for supportive/contradictive nuance
    --batch-size 25 \
    --min-chars 40

# Fast smoke tests (no API calls)
scitex-scholar highlight paper.pdf --stub

# Dry run (classify but don't write PDF)
scitex-scholar highlight paper.pdf --dry-run

# Offline-label workflow (for manual or reviewer-in-the-loop annotation)
scitex-scholar highlight paper.pdf --labels-dump blocks.json     # extract only
#   ... edit blocks.json, produce labels.json with {id, category, confidence} ...
scitex-scholar highlight paper.pdf --labels-apply labels.json    # no LLM call
```

The module is also runnable as a standalone entrypoint:

```bash
python -m scitex_scholar.pdf_highlight paper.pdf
```

## Python API

```python
from scitex_scholar.pdf_highlight import (
    highlight_pdf,          # one-shot: extract → classify → annotate → save
    extract_blocks,         # stage 1 only
    apply_classifications,  # merge offline labels into already-extracted blocks
    save_with_highlights,   # stage 3 only (apply labels → write PDF)
)

# One-shot (default: sentence-level, Haiku, legend page on)
result = highlight_pdf(
    "paper.pdf",
    output_path="paper.highlighted.pdf",
    model="claude-haiku-4-5-20251001",
)
print(result.counts(), result.annotations_added)

# Offline / reviewer workflow
doc, blocks = extract_blocks("paper.pdf", sentence_level=True)
# ...produce labels from any source: LLM, human, rule-based, combinations...
apply_classifications(blocks, [
    {"id": 42, "category": "focal_claim",  "confidence": 0.95},
    {"id": 43, "category": "focal_method", "confidence": 0.80},
])
save_with_highlights(doc, blocks, "paper.highlighted.pdf",
                     model_label="manual", source_name="paper.pdf")
```

## Model selection

| model | wall time on 8-page paper | cost tier | strengths |
|---|---|---|---|
| `claude-haiku-4-5-20251001`  | ~10 s paragraph / ~40 s sentence | cheap   | structural tagging (method/claim/limitation) |
| `claude-sonnet-4-6`          | ~17 s paragraph / ~70 s sentence | mid     | catches subtle supportive/contradictive stances in related work |

Use Haiku for library-wide scans, escalate to Sonnet only when the supportive/contradictive axis matters for a specific paper.

## Known limitations

- **Block-level first pass.** Extraction uses PyMuPDF's paragraph blocks as the clip region for each sentence. Multi-column papers are handled, but pathological layouts (wrapped tables, pull-quotes) may produce skewed rectangles. When the Java-based [opendataloader-pdf](https://github.com/opendataloader-project/opendataloader-pdf) is available, its XY-Cut++ reading order gives better paragraph segmentation; the extractor is structured to allow that swap.
- **Sentence splitter is regex-based.** Handles common academic abbreviations (Fig., e.g., et al., single-initial J.) but is not a full statistical splitter. Edge cases fall back to line-level quads (still tight — no margin inflation).
- **Single label per sentence.** A sentence that both describes a method and reports what the method found gets the higher-priority label (claim wins over method per the prompt). Overlapping annotations would be possible but are not currently emitted.
- **No self-citation detection.** "Cook et al. (11)" where (11) is the same first author as the focal paper is tagged as `related_supportive` when the sentence endorses it, even though mechanically it is self-citation.

## Library scan (all NeuroVista PDFs)

```python
from pathlib import Path
from scitex_scholar.pdf_highlight import highlight_pdf

for p in Path("~/.scitex/scholar/library/neurovista").expanduser().glob("PDF-*/*.pdf"):
    out = p.with_name(p.stem + ".highlighted.pdf")
    if out.exists():
        continue
    try:
        highlight_pdf(p, output_path=out)
    except Exception as exc:        # keep scanning on per-file failure
        print(f"[skip] {p.name}: {exc}")
```
