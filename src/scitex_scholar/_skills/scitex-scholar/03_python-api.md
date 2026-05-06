---
description: |
  [TOPIC] scitex-scholar Python API
  [DETAILS] Top-level public callables — Scholar, Paper, Papers, ScholarConfig, ScholarAuthManager, ScholarBrowserManager, citation graph, formatters, migration helpers.
tags: [scitex-scholar-python-api]
---

# Python API

Top-level public surface re-exported from `scitex_scholar`.

## Core classes

| Name                 | Purpose                                                    |
|----------------------|------------------------------------------------------------|
| `Scholar`            | Main facade — search, enrich, download, organise           |
| `Paper`              | Single paper (metadata + PDF + BibTeX entry)               |
| `Papers`             | Collection of `Paper` (filter, dedup, save BibTeX)         |
| `ScholarConfig`      | Config loader (env + YAML) for scholar                     |
| `ScholarAuthManager` | OpenAthens / SSO session management                        |
| `ScholarBrowserManager` | Playwright browser pool for PDF download                |
| `ScholarURLFinder`   | Resolve OpenURL / publisher landing pages                  |

## Citation graph

| Name                  | Purpose                                  |
|-----------------------|------------------------------------------|
| `CitationGraphBuilder`| Build citation networks from a corpus    |
| `plot_citation_graph` | Render the network                       |

## Formatting / export

| Name                | Purpose                                        |
|---------------------|------------------------------------------------|
| `to_bibtex`         | Papers / dict → BibTeX string                  |
| `to_endnote`        | → EndNote                                      |
| `to_ris`            | → RIS                                          |
| `to_text_citation`  | → human citation string                        |
| `make_citation_key` | Stable BibTeX key from metadata                |
| `generate_cite_key` | Alias used by older code                       |
| `papers_to_format`  | Generic formatter dispatch                     |

## Migration helpers

| Name                     | Purpose                                |
|--------------------------|----------------------------------------|
| `from_connected_papers`  | Import a Connected Papers JSON         |
| `to_connected_papers`    | Export to Connected Papers schema      |

## Filters / utilities

| Name             | Purpose                                                  |
|------------------|----------------------------------------------------------|
| `apply_filters`  | Apply year / journal / quartile filters to `Papers`      |
| `clean_abstract` | Normalise whitespace / encoding in abstract text         |

See `05_api-overview.md` for storage layout and subpackages.

## Concrete examples

```python
from scitex_scholar import (
    Scholar, Paper, Papers, ScholarConfig, ScholarAuthManager,
    apply_filters, to_bibtex, to_ris, to_endnote, to_text_citation,
    generate_cite_key, make_citation_key,
)

# Scholar facade
scholar = Scholar()
papers  = scholar.search("seizure forecasting", limit=20)
paper   = scholar.fetch(doi="10.1093/brain/awx173", project="NeuroVista")

# Papers collection
papers = Papers.from_bibtex("refs.bib")
papers = papers.filter(year_min=2018)
papers.save("filtered.bib")
papers.save("filtered.csv")

# Paper record
p = Paper(doi="10.1093/brain/awx173")
p.enrich()                         # fills metadata in-place
p.download(project="NeuroVista")   # PDF

# Config
cfg = ScholarConfig()
cfg.library_dir          # ~/.scitex/scholar/library
cfg.cache_dir

# Auth
auth = ScholarAuthManager()
auth.check_status(method="openathens", verify_live=True)
auth.authenticate(method="openathens", institution="University of Melbourne")
auth.logout(method="openathens")

# Citation keys & formatting
key = generate_cite_key(author="Karoly", year=2017, title="The circadian profile...")
to_bibtex(papers); to_ris(papers); to_endnote(papers); to_text_citation(papers)

# Filters
hits = apply_filters(papers, year_min=2020, journals=["Nature Communications", "Brain"])
```
