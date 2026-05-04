---
description: |
  [TOPIC] Mcp Tools
  [DETAILS] search, DOI, enrichment, PDF, library.
tags: [scitex-scholar-mcp-tools, scitex-scholar]
---


# MCP Tools

| Tool | Description |
|------|-------------|
| `scholar_authenticate` | Start SSO login (OpenAthens / Shibboleth) |
| `scholar_check_auth_status` | Check session validity (optionally `verify_live`) |
| `scholar_logout` | Clear cached auth |
| `scholar_search_papers` | Search local + external databases |
| `scholar_resolve_dois` | Title → DOI (resumable) |
| `scholar_resolve_openurls` | DOI → publisher URL via institutional OpenURL |
| `scholar_enrich_bibtex` | Add metadata fields with provenance |
| `scholar_parse_bibtex` | Parse BibTeX to structured records |
| `scholar_download_pdfs_batch` | Download many PDFs in parallel (resumable) |
| `scholar_validate_pdfs` | PDF integrity + title match |
| `scholar_parse_pdf_content` | Extract sections / text from a PDF |
| `scholar_export_papers` | Export to BibTeX / RIS / EndNote / CSV |
| `scholar_create_project` | Create a project |
| `scholar_list_projects` | List projects |
| `scholar_add_papers_to_project` | Attach DOIs / BibTeX entries to project |
| `scholar_get_library_status` | Library + project stats |
| `scholar_fetch_papers` | One-shot pipeline (resolve → enrich → download) |
| `scholar_start_job` | Start an async pipeline job |
| `scholar_get_job_status` | Poll a job |
| `scholar_get_job_result` | Fetch a finished job's result |
| `scholar_list_jobs` | List jobs (running / completed) |
| `scholar_cancel_job` | Cancel a running job |
