---
description: |
  [TOPIC] scitex-scholar CLI Reference
  [DETAILS] Top-level noun-verb subcommand groups of the `scitex-scholar` CLI — paper, bibtex, mcp, pdf, library.
tags: [scitex-scholar-cli-reference]
---

# CLI Reference

`scitex-scholar` is the entry point installed by `pip install scitex-scholar`.

## Top-level groups (noun-verb grammar)

| Group     | Verb / sub-noun                                | Purpose                                                |
|-----------|------------------------------------------------|--------------------------------------------------------|
| `paper`   | `process`                                      | Process one paper (DOI or title)                       |
| `paper`   | `batch`                                        | Process many papers concurrently                       |
| `bibtex`  | `process`                                      | Process every entry in a `.bib` file                   |
| `mcp`     | `start`, `list-tools`, `doctor`, `install`     | MCP server commands                                    |
| `pdf`     | `highlight`                                    | Overlay semantic highlights on a PDF                   |
| `library` | `link-project-tree`                            | Symlink a project's `.scitex/scholar/library`          |
| `library` | `materialize`                                  | Replace a library symlink with a real bib-filtered dir |
| `library` | `dematerialize`                                | Replace a materialized dir with a symlink              |
| `library` | `db {build,migrate,lookup,list,dedupe,audit}`  | Manage the library SQLite index                        |

Run `scitex-scholar <group> --help` to discover verbs.

## Library layout

```
~/.scitex/scholar/library/
  MASTER/{8DIGITID}/   # canonical storage (no duplicates)
  {project}/           # project symlinks into MASTER
```

## Examples

```bash
scitex-scholar paper process --doi 10.1038/s41586-020-2649-2 --project demo
scitex-scholar paper batch   --dois 10.1038/x 10.1126/y --project demo --num-workers 4
scitex-scholar bibtex process --bibtex refs.bib --project demo
scitex-scholar mcp start
scitex-scholar pdf highlight paper.pdf
scitex-scholar library link-project-tree .
scitex-scholar library db audit
```

## Migration from pre-1.3.0

The pre-1.3.0 top-level commands still parse, emit a one-line
`DeprecationWarning` on stderr, and dispatch to the same handler. They will be
**removed in 1.4.0**.

| Old (deprecated)                          | New (1.3.0+)                              |
|-------------------------------------------|-------------------------------------------|
| `single`                                  | `paper process`                           |
| `parallel`                                | `paper batch`                             |
| `bibtex --bibtex …`                       | `bibtex process --bibtex …`               |
| `highlight`                               | `pdf highlight`                           |
| `link-project-tree`                       | `library link-project-tree`               |
| `materialize`                             | `library materialize`                     |
| `dematerialize`                           | `library dematerialize`                   |
| `db {…}`                                  | `library db {…}`                          |
