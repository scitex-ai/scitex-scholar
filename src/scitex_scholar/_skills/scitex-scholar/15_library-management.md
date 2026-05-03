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
├── MASTER/                     # canonical storage — one entry per paper
│   └── {8DIGIT-HEX-ID}/
│       ├── {publisher-name}.pdf
│       ├── attachments/...
│       ├── metadata.json
│       └── screenshots/{ts}-{stage}.jpg
└── {project}/
    ├── info/
    │   └── files-bib/summary.csv     # per-project summary
    ├── {8DIGIT-HEX-ID} -> ../MASTER/{8DIGIT-HEX-ID}
    └── ...
```

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
