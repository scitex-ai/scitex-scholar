# SciTeX Scholar (<code>scitex-scholar</code>)

<p align="center">
  <a href="https://scitex.ai">
    <img src="docs/scitex-logo-banner.png" alt="SciTeX Scholar" width="400">
  </a>
</p>

<p align="center"><b>Scientific paper search, enrichment, download, and management for reproducible research</b></p>

<p align="center">
  <a href="https://badge.fury.io/py/scitex-scholar"><img src="https://badge.fury.io/py/scitex-scholar.svg" alt="PyPI version"></a>
  <a href="https://github.com/ywatanabe1989/scitex-scholar/actions/workflows/test.yml"><img src="https://github.com/ywatanabe1989/scitex-scholar/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
</p>

<p align="center">
  <code>pip install scitex-scholar</code>
</p>

---

## Problem

Managing scientific literature programmatically requires juggling multiple tools and APIs: searching across databases, resolving DOIs, downloading PDFs through institutional access, enriching BibTeX metadata, and organizing everything in a reproducible structure. Each step involves different libraries, authentication flows, and data formats.

## Solution

scitex-scholar provides a unified interface for the full literature management workflow:

- **Search** across Google Scholar, Semantic Scholar, PubMed, and CrossRef
- **Enrich** BibTeX entries with abstracts, DOIs, citation counts, and impact factors
- **Download** PDFs through institutional access (OpenAthens) with browser automation
- **Organize** papers in a structured library with deduplication and metadata

## Installation

```bash
pip install scitex-scholar
```

With optional dependencies:

```bash
pip install scitex-scholar[pdf]     # PDF parsing
pip install scitex-scholar[mcp]     # MCP server for AI agents
pip install scitex-scholar[all]     # Everything
```

## Usage

```python
from scitex_scholar import Scholar, Paper, Papers

# Search for papers
scholar = Scholar()
papers = scholar.search("deep learning EEG")

# Export as BibTeX
papers.save("results.bib")

# Enrich metadata
from scitex_scholar import to_bibtex, generate_cite_key
bibtex = to_bibtex(papers)
```

## Core API

| Class / Function | Purpose |
|-----------------|---------|
| `Scholar` | Main search and management interface |
| `Paper` | Single paper with metadata |
| `Papers` | Collection of papers with export methods |
| `ScholarConfig` | Configuration (paths, API keys) |
| `to_bibtex` | Export to BibTeX format |
| `generate_cite_key` | Generate citation keys |
| `apply_filters` | Filter paper collections |

## License

AGPL-3.0
