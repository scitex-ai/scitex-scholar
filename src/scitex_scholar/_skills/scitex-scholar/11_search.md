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

## GUI / Python local Crossref pages

With only **Crossref (SciTeX)** selected, GUI Search uses `api/search/page` and
**Load more**. Its source count precedes filters/deduplication; do not describe it
as the count of matching filtered papers. Online/multiple-source search remains
bounded and has no global total.

```python
from scitex_scholar import ScholarSearchEngine

engine = ScholarSearchEngine()
import asyncio
page = asyncio.run(engine.search_page("hippocampus", offset=1000, page_size=50))
next_offset = page["metadata"]["pagination"]["next_offset"]
```

There is no total-result cap on this local page route. Each request is limited
to 1–1000 source records; follow the returned offset explicitly rather than
starting an automatic all-corpus download. See the installed
[page provider](../../search_engines/_crossref_pages.py) and checkout document
`docs/gui/search-pages.md`. Regression coverage for this contract lives in
`tests/scitex_scholar/search_engines/test__crossref_pages.py` and
`tests/scitex_scholar/_django/test_views_search_pages.py`. This does not claim all-results virtualization or bounded browser
memory across arbitrarily many loaded pages.

## Seeding citation graphs

Select works in Search or Library, then choose **Graph** / **Graph selected**.
Library selection survives sorting. A graph accepts 1–20 distinct valid DOIs;
larger selections are refused with a visible message, not silently truncated.
The Citation Graph tab offers links back to those selection tabs and puts its
visualization above the saved Graph Library. Selecting works does not itself
save papers or graphs.

Graph Library saves rebuild recipes (the seed DOI list and `top_n`), not frozen
node/edge/layout snapshots. Loading uses the current configured citation
backend. Mounted files live in the host-provided user's
`.scitex/scholar/library/SAVED_GRAPHS/saved_graphs.json`; existing empty files
remain authoritative over stale mirror rows. See
the installed [persistence implementation](../../citation_graph/_saved_graph_store.py)
and checkout document `docs/gui/graph-library.md` for provider precedence, legacy
migration, and the fact that listing can maintain its mirror.
