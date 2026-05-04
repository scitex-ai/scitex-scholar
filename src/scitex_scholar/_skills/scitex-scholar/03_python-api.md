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

See `07_python-api.md` for the legacy reference, and
`05_api-overview.md` for storage layout and subpackages.
