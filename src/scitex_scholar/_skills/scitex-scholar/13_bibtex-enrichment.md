---
description: |
  [TOPIC] Bibtex Enrichment
  [DETAILS] Enrich BibTeX entries with metadata (abstract, citations, IF) and per-field provenance.
tags: [scitex-scholar-bibtex-enrichment, scitex-scholar]
---


# BibTeX Enrichment

Adds missing fields (abstract, citation count, journal impact factor, ISSN, etc.) to a BibTeX file by querying CrossRef + OpenAlex + Semantic Scholar.

## CLI

```bash
python -m scitex_scholar.enrich_bibtex /path/to/refs.bib
# → /path/to/refs_enriched.bib
# → /path/to/refs_enriched.csv
```

## MCP

```
scholar_enrich_bibtex(bibtex_path="refs.bib", project=None, sources=[...])
```

## Provenance — every field carries its source

```bibtex
@article{Karoly2017,
  title         = {The circadian profile of epilepsy improves seizure forecasting},
  title_source  = {crossref},
  abstract      = {...},
  abstract_source = {openalex},
  citations     = {412},
  citations_source = {semantic_scholar},
  doi           = {10.1093/brain/awx173},
  doi_source    = {crossref},
  ...
}
```

When two sources disagree, the enricher prefers the more authoritative one (CrossRef for DOI/title, Semantic Scholar for citations) and keeps the loser as `<field>_alt`.

## Skipped fields

- Once a field is populated, enrichment never overwrites it (assumes original is intentional)
- `journal_rank` and `h_index` are intentionally NOT added (out of scope)

## Resumable

Per-entry state in `~/.scitex/scholar/cache/enrich/<bibkey>.json`. Re-running picks up after the last completed entry.
