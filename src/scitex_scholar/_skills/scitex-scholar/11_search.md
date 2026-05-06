---
description: |
  [TOPIC] Search
  [DETAILS] Search papers across local library and external databases.
tags: [scitex-scholar-search, scitex-scholar]
---


# Search

## Sources

| Source | Coverage | Notes |
|--------|----------|-------|
| `local` | Your library | Metadata + full-text (if PDF parsed) |
| `crossref` | 167M+ works | DOI authority; via crossref-local for offline |
| `openalex` | 284M+ works | Abstracts, citations; via openalex-local for offline |
| `semantic_scholar` | ~210M | TLDR summaries, embeddings |
| `pubmed` | Biomedical | MeSH terms |
| `arxiv` | Preprints | Full PDFs always available |

## Python

```python
from scitex_scholar import Scholar

scholar = Scholar()

# Local library
papers = scholar.search("seizure prediction")

# External, multi-source
papers = scholar.search(
    "circadian seizure forecasting",
    sources=["crossref", "openalex", "semantic_scholar"],
    year_min=2018,
    year_max=2025,
    limit=50,
)
papers.save("hits.bib")
```

## CLI / MCP

```
scholar_search_papers(query, search_mode="local"|"external", sources=[...], year_min=, year_max=, limit=20)
```

## Local databases (offline, fast)

When the full-text databases are present, prefer them over the live APIs:

```bash
scitex scholar crossref-scitex search "seizure forecasting" --limit 10
scitex scholar openalex-scitex  search "seizure forecasting" --limit 10
```

See [crossref-local](../../crossref-local/SKILL.md) and [openalex-local](../../openalex-local/SKILL.md) skills.
