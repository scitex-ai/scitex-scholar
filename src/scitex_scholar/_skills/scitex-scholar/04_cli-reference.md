---
description: |
  [TOPIC] scitex-scholar CLI Reference
  [DETAILS] Top-level subcommands of the `scitex-scholar` CLI — single, parallel, bibtex, mcp, link-project-tree, materialize, dematerialize, db, highlight.
tags: [scitex-scholar-cli-reference]
---

# CLI Reference

`scitex-scholar` is the entry point installed by `pip install scitex-scholar`.

## Subcommands

| Command            | Purpose                                                       |
|--------------------|---------------------------------------------------------------|
| `single`           | Process one paper (DOI or title)                              |
| `parallel`         | Process many papers concurrently                              |
| `bibtex`           | Process papers from a `.bib` file (resolve, enrich, download) |
| `mcp`              | Start the MCP server (stdio) for AI agents                    |
| `link-project-tree`| Symlink a project's `.scitex/scholar/library` to the home library |
| `materialize`      | Replace a library symlink with a real, bib-filtered directory |
| `dematerialize`    | Replace a materialized directory with a symlink               |
| `db`               | Manage the library SQLite index                               |
| `highlight`        | Overlay semantic highlights on a PDF                          |

## Library layout

```
~/.scitex/scholar/library/
  MASTER/{8DIGITID}/   # canonical storage (no duplicates)
  {project}/           # project symlinks into MASTER
```

## Example

```bash
scitex-scholar bibtex papers.bib --project myresearch
scitex-scholar mcp                 # speak MCP/stdio for an AI agent
scitex-scholar single 10.1038/s41586-020-2649-2
```

See `08_cli-reference.md` for extended option-level reference.
