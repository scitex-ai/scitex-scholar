---
name: scitex-scholar
description: Scientific literature management with paper search, DOI resolution, BibTeX enrichment, PDF downloading, and library management. Use when searching papers, managing references, or enriching bibliographies.
allowed-tools: mcp__scitex__scholar_*
---

# Literature Management with scitex-scholar

## Quick Start

```python
# Via unified MCP server (recommended)
# Tools: scholar_search_papers, scholar_enrich_bibtex, scholar_fetch_papers

# Via CLI
scitex scholar search "neural oscillations" --limit 20
scitex scholar bibtex papers.bib --enrich
```

## Common Workflows

### "Search for papers"

```bash
# Search across databases
scitex scholar search "deep learning EEG" --limit 50

# Via MCP
scholar_search_papers(query="deep learning EEG", limit=50)
```

### "Enrich my BibTeX"

```bash
# Add abstracts, DOIs, impact factors
scitex scholar bibtex references.bib --enrich
scitex-writer bib enrich references.bib

# Via MCP
scholar_enrich_bibtex(bibtex_path="references.bib")
```

### "Resolve DOIs from titles"

```python
# Via MCP
scholar_resolve_dois(titles=["Attention Is All You Need"])
```

### "Download PDFs"

```python
# Batch download with institutional access
scholar_download_pdfs_batch(
    dois=["10.1038/s41586-024-00001-1"],
    output_dir="./papers/"
)
```

### "Manage paper library"

```python
# Check library status
scholar_get_library_status()

# Create project for organizing papers
scholar_create_project(name="my-review", description="Literature review")
scholar_add_papers_to_project(project="my-review", paper_ids=[...])
```

## MCP Tools (via unified scitex server)

| Tool | Purpose |
|------|---------|
| `scholar_search_papers` | Search across databases |
| `scholar_fetch_papers` | Fetch paper metadata |
| `scholar_resolve_dois` | Resolve DOIs from titles |
| `scholar_resolve_openurls` | Resolve OpenURLs |
| `scholar_enrich_bibtex` | Enrich BibTeX with metadata |
| `scholar_parse_bibtex` | Parse BibTeX file |
| `scholar_parse_pdf_content` | Extract text from PDF |
| `scholar_download_pdfs_batch` | Batch download PDFs |
| `scholar_validate_pdfs` | Validate downloaded PDFs |
| `scholar_get_library_status` | Library status |
| `scholar_create_project` | Create paper project |
| `scholar_add_papers_to_project` | Add papers to project |
| `scholar_list_projects` | List projects |
| `scholar_export_papers` | Export papers |
| `scholar_authenticate` | Authenticate for access |
| `scholar_check_auth_status` | Check auth status |
| `scholar_start_job` | Start async job |
| `scholar_get_job_status` | Check job status |
| `scholar_get_job_result` | Get job result |
