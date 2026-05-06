---
description: |
  [TOPIC] Api Overview
  [DETAILS] Top-level Python API, CLI, MCP tool catalog, storage layout, and installation extras for scitex-scholar.
tags: [scitex-scholar-api-overview, scitex-scholar]
---


# scitex-scholar API overview

Broad surface-level tour of the package. For deeper topic-specific guides
see the `10_`–`16_` workflow leaves.

## Python API

```python
from scitex_scholar import Scholar, Paper, Papers, ScholarConfig

scholar = Scholar()
papers = scholar.search("deep learning EEG", year_min=2020)   # auto-enriched
papers.save("results.bib")

# Filter + export
from scitex_scholar import apply_filters, to_bibtex, to_ris, to_endnote
top = apply_filters(papers, min_citations=50, min_impact_factor=5.0)
print(to_bibtex(top))
```

Top-level re-exports (`src/scitex_scholar/__init__.py`):

| Symbol | Purpose |
|--------|---------|
| `Scholar` | Main entry point; search, enrich, download, save (mixin-composed) |
| `Paper`, `Papers` | Single paper / collection with filter/sort/export methods |
| `ScholarConfig` | Paths, API keys, auto-enrich toggle, browser settings |
| `apply_filters` | Filter `Papers` by year, citations, impact factor, PDF presence |
| `to_bibtex`, `to_ris`, `to_endnote`, `to_text_citation`, `papers_to_format` | Export formats |
| `generate_cite_key`, `make_citation_key` | Deterministic BibTeX keys |
| `CitationGraphBuilder`, `plot_citation_graph` | Optional citation graph (if deps present) |
| `from_connected_papers`, `to_connected_papers` | Optional Connected Papers bridge |

Core subpackages:

* `core/` — `Scholar`, `Paper`, `Papers`, open-access detection, journal normalisation
* `search_engines/` — `ArXiv`, `CrossRef`, `OpenAlex`, `PubMed`, `SemanticScholar`
* `metadata_engines/` — same sources for DOI resolution + metadata enrichment; `impact_factor` integration (JCR 2024)
* `pdf_download/` — `ScholarPDFDownloader` with multiple strategies
* `pipelines/` — `ScholarPipelineSingle`, `ScholarPipelineParallel`, `ScholarPipelineBibTeX`, metadata/search variants
* `browser/`, `auth/` — Playwright-based browser automation with OpenAthens / institutional SSO
* `storage/`, `local_dbs/` — MASTER-hash storage with project symlinks, local DB indexes
* `filters.py`, `formatting.py` — filtering and BibTeX/RIS/EndNote export
* `citation_graph/`, `migration/`, `zotero/`, `integration/` — optional adapters

## CLI

Entry point: `python -m scitex_scholar <subcommand> [options]` (`src/scitex_scholar/__main__.py`).

```bash
# Single paper by DOI or title
python -m scitex_scholar single --doi 10.1038/nature12373 --project demo

# Batch via titles or DOIs, in parallel
python -m scitex_scholar parallel --dois 10.1038/xxx 10.1126/yyy --num-workers 4 --project demo

# Whole BibTeX file
python -m scitex_scholar bibtex --bibtex refs.bib --project demo --output refs.enriched.bib

# Start the legacy MCP server
python -m scitex_scholar mcp
```

Common flags: `--browser-mode {stealth,interactive}`, `--chrome-profile NAME`, `--force`.

Auxiliary scripts under `src/scitex_scholar/cli/` (`chrome.py`, `open_browser.py`, `download_pdf.py`, etc.) support ad-hoc browser and download workflows.

## MCP tools

`scitex_scholar/mcp_server.py` provides a stand-alone MCP server (marked deprecated in favour of the unified `scitex serve` server, which re-exports the same handlers via `_mcp/all_handlers.py`).

Standard handlers (`_mcp/handlers.py`):

| Tool | Purpose |
|------|---------|
| `search_papers` | Search local library + external databases (crossref, semantic_scholar, pubmed, arxiv, openalex) |
| `resolve_dois` | DOI resolution from titles or BibTeX, resumable |
| `enrich_bibtex` | Add DOIs, abstracts, citation counts, impact factors, PMIDs, arXiv IDs |
| `download_pdf` / `download_pdfs_batch` | PDF retrieval via institutional access (OpenAthens) |
| `get_library_status` | Library statistics (papers, projects, PDFs) |
| `parse_bibtex` | Parse a BibTeX file into structured paper records |
| `validate_pdfs` | Validate stored PDFs |
| `resolve_openurls` | Turn DOIs into institution-specific OpenURLs |
| `authenticate` / `check_auth_status` / `logout` | Institutional auth state |
| `export_papers` | Export project papers (bibtex/csv/json) |
| `create_project` / `list_projects` / `add_papers_to_project` | Project management |
| `parse_pdf_content` | Extract text from a stored PDF |

Job-management handlers (`_mcp/job_handlers.py`): `fetch_papers`, `list_jobs`, `get_job_status`, `start_job`, `cancel_job`, `get_job_result`.

Provider-scoped tools:

* `openalex_search`, `openalex_get`, `openalex_count`, `openalex_info` (`_mcp/openalex_handlers.py`)
* `crossref_search`, `crossref_get`, `crossref_count`, `crossref_citations`, `crossref_info` (`_mcp/crossref_handlers.py`)

## Storage layout

```
~/.scitex/scholar/library/
├── MASTER/<HASH>/             # Canonical per-paper storage (metadata.json + PDF)
└── <project>/<human-label> -> ../MASTER/<HASH>   # Per-project symlinks
```

Cache / state lives under `~/.scitex/scholar/cache/` (URL resolver, Chrome profiles, auth cookies). The root respects `SCITEX_DIR`.

## Installation

```bash
pip install scitex-scholar               # core
pip install "scitex-scholar[pdf]"        # pdfplumber for PDF text extraction
pip install "scitex-scholar[mcp]"        # fastmcp MCP server deps
pip install "scitex-scholar[browser]"    # Playwright browser automation
pip install "scitex-scholar[export]"     # openpyxl (.xlsx export)
pip install "scitex-scholar[server]"     # aiohttp/flask (HTTP adapters)
pip install "scitex-scholar[watch]"      # watchdog (library watcher)
pip install "scitex-scholar[all]"        # everything above + dev tooling
```

## Status / caveats

* The standalone `scitex_scholar.mcp_server` is deprecated; prefer the unified `scitex serve` server exposing the same handlers with `scholar_*` prefixes.
* PDF download through institutional proxies requires a one-time interactive login (`python -m scitex_scholar single --browser-mode interactive …` or the `chrome` helper).
* Some CLI helpers in `src/scitex_scholar/cli/*.py` are experimental / internal and not part of the stable public API — prefer the documented subcommands.
