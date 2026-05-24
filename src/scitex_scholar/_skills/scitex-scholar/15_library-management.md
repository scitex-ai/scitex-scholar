---
description: |
  [TOPIC] Library Management
  [DETAILS] MASTER/{ID} hash storage, project symlinks, metadata.json layout.
tags: [scitex-scholar-library-management, scitex-scholar]
---


# Library Management

## Layout

```
~/.scitex/scholar/library/
├── MASTER/                                      # canonical storage
│   └── {8DIGIT-HEX-ID}/
│       ├── <First>-<Year>-<Journal>.pdf         # main PDF (chmod 444)
│       ├── supple-<original_name>.pdf           # supplementary (repeatable)
│       ├── additional-<original_name>.<ext>     # attachments (repeatable)
│       ├── metadata.json                        # incl. path.files registry
│       └── screenshots/{ts}-{stage}.jpg
└── {project}/
    ├── info/
    │   ├── project_metadata.json                # last_refresh, syncs ledger
    │   └── files-bib/summary.csv                # per-project summary
    ├── PDF-NN_CC-NNNNNN_IF-NNN_YYYY_Author_Journal -> ../MASTER/{ID}
    └── ...
```

### File-role registry (`metadata.path.files`)

Every imported file is recorded as:

```json
{"role": "main|supplementary|additional",
 "name": "<on-disk-name>",
 "sha256": "...",
 "size": 5278199,
 "added_at": "2026-05-08T...Z",
 "source": "/original/path",
 "immutable": true}
```

Main PDFs are `chmod 444` on import (Zotero-style: the canonical
record-of-paper file stays read-only; annotated copies live next to it
under their own `notes-…pdf` / `supple-…pdf`). `library audit-files`
verifies presence + SHA-256 across all roles.

The 8-digit ID is a deterministic hash of `(normalized_title, first_author, year)`, so the *same paper* added to multiple projects always resolves to the same MASTER entry — no duplication, no wasted disk.

## Why MASTER + symlinks

- A paper cited in three projects costs disk only once
- Re-enrichment in any project is visible everywhere
- `rm -rf ~/.scitex/scholar/library/{project}` is a safe project deletion (MASTER untouched)

## Projects

```
scholar_create_project(project_name, description=None)
scholar_list_projects()
scholar_add_papers_to_project(project, dois=[...] | bibtex_path=...)
scholar_get_library_status()
```

## metadata.json

Each MASTER entry stores:
- DOI, title, authors, year, journal
- Source-tagged enrichment (`<field>_source`)
- All URLs traversed (publisher, OpenURL, PDF)
- Download timestamps, Zotero translator used
- File hashes for integrity check

## Pending / failed entries

Failed downloads keep the metadata entry but no PDF. They appear in:

```
~/.scitex/scholar/library/{project}/info/pending.txt
```

with the reason (e.g. `IEEE - not subscribed`, `CAPTCHA`, `In Chrome for Zotero`).

## CLI verbs ([Daily] / [Layout] / [Share] / [Database])

```bash
# Daily
scitex-scholar library list                  # totals across projects
scitex-scholar library list neurovista       # one project, per-paper
scitex-scholar library open-urls neurovista --watch
scitex-scholar library refresh [PROJECT] [--sync HOST]

# Layout
scitex-scholar library bind PROJECT PROJECT-DIR     # one symlink, no data move
scitex-scholar library PROJECT PROJECT-DIR          # bind shorthand
scitex-scholar library link-project-tree            # whole-library view
scitex-scholar library materialize / dematerialize  # bib-filtered

# Share
scitex-scholar library sync HOST [--project P] [--remote-path PATH]
scitex-scholar library export PROJECT --format bibtex|tarball|flat-pdfs
scitex-scholar library zotero {import,export,diff}

# Database / integrity
scitex-scholar library db {build,migrate,lookup,list,audit}
scitex-scholar library audit-files [--project P]
```

## Manual PDF import (no automatic download)

When metadata indices haven't yet caught up to a fresh paper or the
publisher blocks scripted downloads, use `paper fetch --pdf-main`:

```bash
scitex-scholar paper fetch --doi 10.1002/epi.70076 \
    --pdf-main ~/Downloads/Liu_2026.pdf \
    --pdf-supple ~/Downloads/41467_2020_15908_MOESM1_ESM.pdf \
    --attachment ~/Downloads/dataset.csv \
    --project neurovista
```

The pipeline skips the browser/download stack, runs metadata
enrichment from the DOI, copies each file under its role-prefixed name
into MASTER, and (for `--pdf-main`) checks the PDF's page-1 DOI
against the metadata to catch silent swaps.
