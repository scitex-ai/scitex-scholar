---
description: |
  [TOPIC] Cli Reference
  [DETAILS] CLI commands for scitex-scholar.
tags: [scitex-scholar-cli-reference, scitex-scholar]
---


# CLI Reference

Two CLIs ship with this package:

- `scitex-scholar` — direct invocation (calls `python -m scitex_scholar`)
- `scitex scholar` — sub-command of the unified `scitex` CLI

## scitex-scholar

```bash
scitex-scholar single   --doi DOI [--project NAME] [--browser-mode stealth|interactive] [--force]
scitex-scholar single   --title "..." [--project NAME]
scitex-scholar parallel --dois DOI1 DOI2 ... [--num-workers N]
scitex-scholar bibtex   --bibtex FILE [--project NAME] [--output FILE] [--num-workers N] [--browser-mode ...]
scitex-scholar mcp      [start|doctor]
```

## scitex scholar

```bash
scitex scholar config                        # Show config + library status
scitex scholar fetch DOI [DOI...]            # Fetch papers (resolve+enrich+download)
scitex scholar fetch --from-bibtex FILE -p PROJECT
scitex scholar library                       # Show library
scitex scholar jobs list                     # Background jobs
scitex scholar crossref-scitex search "..."  # Local CrossRef DB
scitex scholar openalex-scitex search "..."  # Local OpenAlex DB
scitex scholar mcp start                     # Start MCP server
scitex scholar gui                           # Launch web GUI
scitex scholar list-python-apis              # Introspect Python API
```

## Common flags

| Flag | Meaning |
|------|---------|
| `-p, --project NAME` | Organize output under this project |
| `--browser-mode stealth\|interactive` | Headless vs visible Chrome |
| `--chrome-profile NAME` | Sync from a named Chrome profile |
| `-w, --workers N` | Parallelism |
| `-f, --force` | Re-download even if cached |
| `--async` | Run in background; query via `jobs` |
| `--dry-run` | Plan only |
| `--json` | Structured Result envelope |
