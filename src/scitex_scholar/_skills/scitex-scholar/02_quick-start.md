---
description: |
  [TOPIC] scitex-scholar Quick Start
  [DETAILS] Smallest useful example — search and save BibTeX in three lines via the Scholar facade.
tags: [scitex-scholar-quick-start]
---

# Quick Start

## Minimal search-and-save

```python
from scitex_scholar import Scholar

scholar = Scholar()
papers = scholar.search("phase-amplitude coupling hippocampus")
papers.save("results.bib")
```

`Scholar()` reads `~/.scitex/scholar/config.yaml` plus `SCITEX_SCHOLAR_*`
env vars (see `20_env-vars.md`). `papers` is a `Papers` collection with
metadata enrichment, BibTeX export, and library-aware methods.

## BibTeX-batch enrichment

```python
from scitex_scholar import Scholar

papers = Scholar().enrich_bibtex("input.bib")
papers.save("output.bib")
```

Resolves DOIs from titles, fills missing abstracts / impact factors, and
writes a clean BibTeX with provenance comments.

## CLI — single paper

```bash
# By DOI
scitex-scholar single --doi "10.1093/brain/awx173" --project NeuroVista

# By title (resolves DOI automatically)
scitex-scholar single --title "Critical slowing down as a biomarker for seizure susceptibility" \
                      --project NeuroVista
```

## CLI — BibTeX batch

```bash
scitex-scholar bibtex --bibtex /path/to/refs.bib \
                      --project NeuroVista \
                      --browser-mode stealth \
                      --num-workers 4
```

The pipeline parses BibTeX → resolves missing DOIs → resolves OpenURL →
downloads PDFs → stores under `MASTER/{ID}/` with project symlinks.
All long-running operations checkpoint per-paper and resume on re-run.

## Browser modes

- `stealth` — headless Chrome with anti-bot evasion (default for batches)
- `interactive` — visible browser; use when CAPTCHA or SSO MFA expected

## Where files land

Library at `~/.scitex/scholar/library/MASTER/{8DIGIT-ID}/`, with
project-scoped symlinks under `~/.scitex/scholar/library/{project}/`.
See `15_library-management.md`.

## Next steps

- `03_python-api.md` — full API surface
- `04_cli-reference.md` — `scitex-scholar single|parallel|bibtex|mcp|...`
- `15_library-management.md` — storage layout details
