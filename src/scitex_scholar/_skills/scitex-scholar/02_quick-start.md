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

## Where files land

Library at `~/.scitex/scholar/library/MASTER/{8DIGIT-ID}/`, with
project-scoped symlinks under `~/.scitex/scholar/library/{project}/`.
See `15_library-management.md`.

## Next steps

- `06_quick-start.md` — extended workflows (parallel, BibTeX, projects)
- `07_python-api.md` — full API surface
- `08_cli-reference.md` — `scitex-scholar single|parallel|bibtex|mcp|...`
