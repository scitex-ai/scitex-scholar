# ADR-100: Project-tree link and library materialization

- **Status:** Accepted
- **Date:** 2026-04-20
- **Context:** scitex-scholar + downstream consumers (one-way)

## Context

Scholar stores its library at `~/.scitex/scholar/library/` with the layout:

```
~/.scitex/scholar/library/
├── MASTER/<paper_id>/           authoritative entries
│   ├── metadata.json
│   ├── <author>-<year>-<journal>.pdf
│   ├── content.txt
│   └── images/, screenshots/, logs/
├── <project_name>/              decorated symlinks → MASTER/…
└── downloads/
```

Downstream tools (LaTeX writers, reference browsers, IDE integrations)
need read access to this library without taking a hard Python dependency
on scitex-scholar. They must also be able to vendor a subset of the
library into a project directory for portability (tarball handoff,
offline compilation).

## Decision

Scholar exposes two symlink-oriented CLI commands. Each takes a generic
filesystem path; neither command mentions any consumer by name.

### 1. `scitex scholar link-project-tree <dir>`

Creates `<dir>/.scitex/scholar/library → ~/.scitex/scholar/library/` as
an absolute symlink (idempotent; `--force` replaces a differing target).
The command performs no other filesystem operations inside `<dir>`.

### 2. `scitex scholar materialize <dir> --bib <path>` (PR-B)

Replaces the symlink target at a consumer-provided path with a real
directory containing a bib-filtered subset of `MASTER/`. Reverses via
`dematerialize`.

### 3. Zotero-style `index.db` (PR-C)

`~/.scitex/scholar/library/index.db` — a SQLite index of MASTER contents
for fast lookup by DOI / arXiv / PMID / citation key, with schema
co-reviewed by known downstream consumers.

## Rationale

- **Filesystem as API.** Consumers read `metadata.json` directly. No
  Python import surface to version.
- **One-way coupling.** Scholar never imports a consumer. Each CLI takes
  a generic path argument.
- **Dangling symlinks tolerated.** A consumer may create the link on a
  machine where scholar has never run; scholar's CLI simply won't have
  been invoked yet. Consumer handles the `ENOENT` gracefully.
- **Materialize for portability.** When a user ships a project tarball
  to a collaborator who does not have scholar, a real directory of the
  cited subset ships with it.

## Consequences

- Scholar commits to keeping `metadata.json` schema stable (additive
  changes only; never rename or remove existing fields).
- `MASTER/<paper_id>/` directory layout is part of the public contract.
- The `<project_name>/` symlink naming scheme remains internal to
  scholar; consumers resolve papers by `paper_id`, not by decorated
  symlink name.

## Non-goals

- Scholar does not provide a Python SDK for consumers. Filesystem +
  (optionally) `index.db` is the API.
- Scholar does not know which consumers exist. Any tool that reads
  `~/.scitex/scholar/library/` is a consumer.
