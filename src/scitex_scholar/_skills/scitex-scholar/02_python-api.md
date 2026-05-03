---
description: |
  [TOPIC] Python Api
  [DETAILS] Scholar, Paper, Papers, ScholarConfig, ScholarAuthManager.
tags: [scitex-scholar-python-api, scitex-scholar]
---


# Python API

```python
from scitex_scholar import (
    Scholar,
    Paper,
    Papers,
    ScholarConfig,
    ScholarAuthManager,
    apply_filters,
    to_bibtex, to_ris, to_endnote, to_text_citation,
    generate_cite_key, make_citation_key,
)
```

## Scholar — top-level facade

```python
scholar = Scholar()                                  # uses ScholarConfig defaults
papers  = scholar.search("seizure forecasting", limit=20)
paper   = scholar.fetch(doi="10.1093/brain/awx173", project="NeuroVista")
```

## Papers — collection

```python
papers = Papers.from_bibtex("refs.bib")
papers = papers.filter(year_min=2018)
papers.save("filtered.bib")
papers.save("filtered.csv")
for p in papers:
    print(p.title, p.doi, p.pdf_path)
```

## Paper — single record

```python
p = Paper(doi="10.1093/brain/awx173")
p.enrich()                  # fills metadata in-place
p.download(project="NeuroVista")   # PDF
p.metadata                  # → dict with provenance
```

## ScholarConfig

Reads `SCITEX_SCHOLAR_*` environment variables; library directory defaults to `$SCITEX_DIR/scholar` (`~/.scitex/scholar`).

```python
cfg = ScholarConfig()
cfg.library_dir
cfg.cache_dir
```

## ScholarAuthManager

```python
auth = ScholarAuthManager()
auth.check_status(method="openathens", verify_live=True)
auth.authenticate(method="openathens", institution="University of Melbourne")
auth.logout(method="openathens")
```

## Citation keys & formatting

```python
key = generate_cite_key(author="Karoly", year=2017, title="The circadian profile...")
to_bibtex(papers); to_ris(papers); to_endnote(papers); to_text_citation(papers)
```

## Filters

```python
hits = apply_filters(papers, year_min=2020, journals=["Nature Communications", "Brain"])
```
