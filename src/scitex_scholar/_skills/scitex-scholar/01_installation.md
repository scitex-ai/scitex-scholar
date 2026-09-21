---
description: |
  [TOPIC] scitex-scholar Installation
  [DETAILS] pip install scitex-scholar with optional extras (browser, pdf, mcp, server, export, watch, clew, all); smoke verify by importing scitex_scholar.
tags: [scitex-scholar-installation]
---

# Installation

## Standard

```bash
pip install scitex-scholar
```

## Optional extras

Two installs exist — core, and everything:

| Install | Contents |
|---|---|
| `pip install scitex-scholar` | core (Playwright browser automation included) |
| `pip install 'scitex-scholar[all]'` | + GUI server (django / scitex-app / scitex-ui), MCP server (fastmcp), PDF text extraction (pdfplumber), XLSX export (openpyxl), library watcher (watchdog), provenance hashing (scitex-clew) |

```bash
pip install scitex-scholar
pip install 'scitex-scholar[all]'
```

## Verify

```bash
python -c "import scitex_scholar; print(scitex_scholar.__version__)"
scitex-scholar --help
```
