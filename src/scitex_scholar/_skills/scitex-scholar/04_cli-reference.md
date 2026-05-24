---
description: |
  [TOPIC] scitex-scholar CLI Reference
  [DETAILS] Top-level Click-based noun-verb subcommand groups of the `scitex-scholar` CLI — paper, bibtex, pdf, library, mcp, skills, list-python-apis.
tags: [scitex-scholar-cli-reference]
---

# CLI Reference

`scitex-scholar` is the Click-based entry point installed by
`pip install scitex-scholar`.

## Universal flags

```bash
scitex-scholar --help                 # top-level help
scitex-scholar --help-recursive       # full overview, every leaf
scitex-scholar -V / --version         # version
scitex-scholar --json …               # machine-readable output (where supported)
```

Mutating verbs accept `--dry-run` and `-y/--yes`. Read verbs (e.g. `mcp
list-tools`, `library db list`, `library db lookup`, `library db audit`,
`skills list`, `list-python-apis`) accept `--json`.

## Top-level groups (categorized in `--help`)

```
[Workflow]
  paper       Operate on a paper / batch of papers
  bibtex      Operate on a BibTeX file
  pdf         PDF post-processing
  library     Library-tree management
  auth        Institutional SSO authentication

[Dev]
  list-python-apis          Public callables in scitex_scholar.__all__
  mcp                       MCP (Model Context Protocol) server commands
  skills                    Bundled skill leaves
  install-shell-completion  Wire <TAB> completion into ~/.{bash,zsh}rc
  print-shell-completion    Print the completion script to stdout
```

| Group                       | Verb / sub-noun                                 | Purpose                                                |
|-----------------------------|-------------------------------------------------|--------------------------------------------------------|
| `paper`                     | `fetch`                                         | Fetch one paper (DOI/title; supports `--pdf-main`)     |
| `paper`                     | `fetch-batch`                                   | Fetch many papers in parallel                          |
| `bibtex`                    | `import`                                        | Import & enrich every entry in a `.bib` file           |
| `pdf`                       | `highlight`                                     | Overlay semantic highlights on a PDF                   |
| `library`                   | `list [PROJECT]`                                | List projects + counts; with PROJECT, per-paper detail |
| `library`                   | `open-urls PROJECT [--watch]`                   | Open paper URLs in browser; auto-import downloads      |
| `library`                   | `refresh [PROJECT] [--sync HOST]`               | Reconcile + regenerate symlinks (+ optional rsync)     |
| `library`                   | `bind PROJECT PROJECT-DIR`                      | Add `<dir>/.scitex/.../<project>` symlink view of home |
| `library`                   | `link-project-tree`                             | Symlink whole project's `.scitex/scholar/library`      |
| `library`                   | `materialize` / `dematerialize`                 | Symlink ↔ real-dir conversion (bib-filtered)           |
| `library`                   | `sync HOST [--remote-path PATH]`                | rsync the library to/from a remote host                |
| `library`                   | `export PROJECT --format FORMAT`                | Export as `bibtex`/`tarball`/`flat-pdfs`/`zotero`      |
| `library`                   | `zotero {import, export, diff}`                 | Bidirectional Zotero migration (local SQLite)          |
| `library`                   | `audit-files`                                   | Verify recorded files vs disk (SHA-256, role-aware)    |
| `library`                   | `db {build,migrate,lookup,list,audit}`          | Manage the library SQLite index                        |
| `auth`                      | `status`, `login`, `logout`, `refresh`          | Institutional SSO session lifecycle                    |
| `mcp`                       | `start`, `list-tools`, `doctor`, `install`      | MCP server commands                                    |
| `skills`                    | `list`, `get`, `install`                        | Bundled skill leaves                                   |
| `list-python-apis`          | —                                               | Print public callables in `scitex_scholar.__all__`     |
| `install-shell-completion`  | —                                               | Wire up `<TAB>` completion                             |
| `print-shell-completion`    | —                                               | Print completion script to stdout                      |

### Shorthand: `library <project> <project-root>`

Verbless dispatch. `library neurovista ~/proj/neurovista` is an alias
for `library bind neurovista ~/proj/neurovista`. Triggers only when
`<project>` already exists under `~/.scitex/scholar/library/`.

## Library layout

```
~/.scitex/scholar/library/
  MASTER/{8DIGITID}/                                     # canonical storage
    <First>-<Year>-<Journal>.pdf                         # main (chmod 444)
    supple-<original_name>.pdf                           # supplementary
    additional-<original_name>.<ext>                     # attachments
    metadata.json                                        # incl. path.files
  {project}/PDF-NN_CC-NNNNNN_IF-NNN_YYYY_Author_Journal  # symlink → MASTER/<id>
```

`metadata.path.files` carries `{role, name, sha256, size, added_at, source, immutable}`
per file, so `audit-files` can detect missing / orphan / hash-mismatch.

## Examples

### Paper fetch — automatic download or local PDF

```bash
# Automatic download
scitex-scholar paper fetch --doi 10.1038/s41586-020-2649-2 --project demo

# DOI accepts URL form (https://doi.org/..., http://dx.doi.org/..., doi:...)
scitex-scholar paper fetch --doi https://doi.org/10.1002/epi.70076 --project demo

# Local main PDF (skips browser; metadata enrichment still runs)
scitex-scholar paper fetch --doi 10.1002/epi.70076 \
    --pdf-main ~/Downloads/Liu_2026.pdf --project neurovista

# With supplementary + attachments (repeatable flags)
scitex-scholar paper fetch --doi 10.1038/s41467-020-15908-3 \
    --pdf-main ~/Downloads/main.pdf \
    --pdf-supple ~/Downloads/41467_2020_15908_MOESM1_ESM.pdf \
    --pdf-supple ~/Downloads/41467_2020_15908_MOESM2_ESM.pdf \
    --attachment ~/Downloads/dataset.csv \
    --project neurovista

scitex-scholar paper fetch-batch --dois 10.1038/x --dois 10.1126/y \
    --project demo --num-workers 4
```

### Library — daily / layout / share / database

```bash
# Daily
scitex-scholar library list                       # all projects, totals
scitex-scholar library list neurovista            # one project, per-paper
scitex-scholar library open-urls neurovista --watch
scitex-scholar library refresh neurovista
scitex-scholar library refresh --sync spartan --sync nas

# Layout
scitex-scholar library bind neurovista ~/proj/neurovista
scitex-scholar library neurovista ~/proj/neurovista     # shorthand

# Share
scitex-scholar library sync spartan --project neurovista \
    --remote-path proj/neurovista/.scitex/scholar/library/neurovista
scitex-scholar library export neurovista --format bibtex
scitex-scholar library export neurovista --format flat-pdfs

# Zotero (engine wired; verify on real round-trip before relying on it)
scitex-scholar library zotero import --project demo --collection demo
scitex-scholar library zotero export --project demo

# Database / integrity
scitex-scholar library db build --dry-run
scitex-scholar library db audit --json
scitex-scholar library audit-files --project neurovista
```

### Other

```bash
scitex-scholar bibtex import --bibtex refs.bib --project demo
scitex-scholar mcp start
scitex-scholar mcp list-tools --json
scitex-scholar pdf highlight paper.pdf --stub
scitex-scholar skills list
scitex-scholar skills install
scitex-scholar list-python-apis -v
```

## Migration from pre-1.3.0

The pre-1.3.0 top-level commands are now hidden Click aliases; they parse,
emit a one-line yellow `DeprecationWarning` on stderr, and dispatch to the
same handler. They will be **removed in 1.4.0**.

| Old (deprecated, hidden)                | New (1.3.0+)                              |
|------------------------------------------|-------------------------------------------|
| `single`                                 | `paper fetch`                             |
| `parallel`                               | `paper fetch-batch`                       |
| `bibtex --bibtex …`                      | `bibtex import --bibtex …`                |
| `highlight`                              | `pdf highlight`                           |
| `link-project-tree`                      | `library link-project-tree`               |
| `materialize`                            | `library materialize`                     |
| `dematerialize`                          | `library dematerialize`                   |
| `db {…}`                                 | `library db {…}`                          |
