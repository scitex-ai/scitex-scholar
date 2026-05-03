---
description: |
  [TOPIC] Pdf Download
  [DETAILS] PDF download via OpenURL → publisher → Zotero translators; stealth and interactive browser modes.
tags: [scitex-scholar-pdf-download, scitex-scholar]
---


# PDF Download

## Pipeline

```
DOI → OpenURL (institutional resolver) → Publisher landing page
    → Zotero translator (per-publisher rules) → PDF URL → download
    → Store under MASTER/{ID}/{original-name}.pdf
```

## CLI

```bash
# Single
scitex-scholar single --doi "10.1093/brain/awx173" --project NeuroVista

# Batch from BibTeX (parallel)
scitex-scholar bibtex --bibtex refs.bib --project NeuroVista \
                      --num-workers 4 --browser-mode stealth
```

## MCP

```
scholar_download_pdfs_batch(dois=[...], project=..., max_concurrent=3, resume=True)
scholar_resolve_openurls(dois=[...])
scholar_validate_pdfs(project=...)
```

## Browser modes

| Mode | When |
|------|------|
| `stealth` | Headless, anti-bot evasion; default for unattended batches |
| `interactive` | Visible window; use when CAPTCHA / MFA / Lean Library prompt expected |

## Required Chrome extensions (auto-installed on first run)

- **Lean Library** — institutional PDF access
- **Zotero Connector** — publisher-specific download rules
- **Accept all cookies** — bypasses consent walls
- **Captcha Solver** — uses `SCITEX_SCHOLAR_2CAPTCHA_API_KEY`

## Storage

```
~/.scitex/scholar/library/MASTER/{8DIGIT}/
  {original-publisher-name}.pdf
  attachments/{supp1}.pdf
  metadata.json                # DOI, title, authors, source URLs
  screenshots/{ts}-{stage}.jpg # browser captures for debugging
```

Project directory has symlinks: `~/.scitex/scholar/library/{project}/{8DIGIT} -> ../MASTER/{8DIGIT}`

## Failure handling

- IEEE / paywalled-without-subscription: skipped, listed for manual download
- MDPI / Frontiers / Nature-family: usually succeed via Zotero translator
- CAPTCHA blocked: switch to `--browser-mode interactive` and solve manually once (cookie cached)
- Skipped entries are reported with `(reason)` and appended to a `pending.txt` for the project

## Validation

```
scholar_validate_pdfs(project="NeuroVista")
```

Checks: PDF magic bytes, page count, file size sanity, and that the title in PDF metadata matches the BibTeX entry (fuzzy).
