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

| Extra      | Adds                                            |
|------------|-------------------------------------------------|
| `browser`  | playwright (OpenAthens / publisher PDF download) |
| `pdf`      | pdfplumber (PDF text + figure extraction)        |
| `mcp`      | fastmcp (expose tools to AI agents)              |
| `server`   | aiohttp + flask (HTTP server mode)               |
| `export`   | openpyxl (XLSX export)                           |
| `watch`    | watchdog (library watch mode)                    |
| `clew`     | scitex-clew (provenance hashing)                 |
| `all`      | every extra above                                |

```bash
pip install 'scitex-scholar[browser,pdf,mcp]'
pip install 'scitex-scholar[all]'
```

## Verify

```bash
python -c "import scitex_scholar; print(scitex_scholar.__version__)"
scitex-scholar --help
```
