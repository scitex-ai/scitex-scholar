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

## Top-level groups

| Group                       | Verb / sub-noun                                 | Purpose                                                |
|-----------------------------|-------------------------------------------------|--------------------------------------------------------|
| `paper`                     | `fetch`                                         | Fetch one paper (DOI or title)                         |
| `paper`                     | `fetch-batch`                                   | Fetch many papers in parallel                          |
| `bibtex`                    | `import`                                        | Import & enrich every entry in a `.bib` file           |
| `pdf`                       | `highlight`                                     | Overlay semantic highlights on a PDF                   |
| `library`                   | `link-project-tree`                             | Symlink a project's `.scitex/scholar/library`          |
| `library`                   | `materialize`                                   | Replace a library symlink with a real bib-filtered dir |
| `library`                   | `dematerialize`                                 | Replace a materialized dir with a symlink              |
| `library`                   | `db {build,migrate,lookup,list,audit}`          | Manage the library SQLite index                        |
| `auth`                      | `status`, `login`, `logout`, `refresh`          | Institutional SSO session lifecycle (OpenAthens etc.)  |
| `mcp`                       | `start`, `list-tools`, `doctor`, `install`      | MCP server commands                                    |
| `skills`                    | `list`, `get`, `install`                        | Bundled skill leaves under `_skills/scitex-scholar/`   |
| `list-python-apis`          | —                                               | Print public callables in `scitex_scholar.__all__`     |
| `install-shell-completion`  | —                                               | Wire up `<TAB>` completion in `~/.bashrc`/`~/.zshrc`   |
| `print-shell-completion`    | —                                               | Print completion script to stdout                      |

## Library layout

```
~/.scitex/scholar/library/
  MASTER/{8DIGITID}/   # canonical storage (no duplicates)
  {project}/           # project symlinks into MASTER
```

## Examples

```bash
scitex-scholar paper fetch --doi 10.1038/s41586-020-2649-2 --project demo
scitex-scholar paper fetch-batch --dois 10.1038/x --dois 10.1126/y --project demo --num-workers 4
scitex-scholar bibtex import --bibtex refs.bib --project demo
scitex-scholar mcp start
scitex-scholar mcp list-tools --json
scitex-scholar pdf highlight paper.pdf --stub
scitex-scholar library link-project-tree .
scitex-scholar library db build --dry-run
scitex-scholar library db audit --json
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
