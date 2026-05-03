---
description: |
  [TOPIC] Quick Start
  [DETAILS] single paper, BibTeX batch, project organization.
tags: [scitex-scholar-quick-start, scitex-scholar]
---


# Quick Start

## Python API

```python
from scitex_scholar import Scholar, Papers

scholar = Scholar()                          # Loads ScholarConfig from env
papers = scholar.search("seizure forecasting", limit=20)
papers.save("results.bib")                   # BibTeX export
```

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

The pipeline:
1. Parses BibTeX → `Paper` objects
2. Verifies SSO auth (prompts if expired)
3. Resolves missing DOIs via CrossRef
4. Resolves publisher URL via OpenURL (institutional access)
5. Downloads PDF via Zotero translators
6. Stores in `~/.scitex/scholar/library/MASTER/{ID}/` and symlinks under the project

## Storage layout

```
~/.scitex/scholar/library/
├── MASTER/{8DIGIT-ID}/
│   ├── {original-name}.pdf
│   ├── attachments/...
│   ├── metadata.json
│   └── screenshots/{timestamp}-{description}.jpg
└── {project}/
    ├── {8DIGIT-ID} -> ../MASTER/{8DIGIT-ID}
    └── info/files-bib/summary.csv
```

## Browser modes

- `stealth` — headless Chrome with anti-bot evasion (default for batches)
- `interactive` — visible browser; use when CAPTCHA or SSO MFA expected

## Resume

All long-running operations checkpoint per-paper and resume on re-run:

```bash
scitex-scholar bibtex --bibtex refs.bib --project p   # interrupted
scitex-scholar bibtex --bibtex refs.bib --project p   # picks up where it left off
```
