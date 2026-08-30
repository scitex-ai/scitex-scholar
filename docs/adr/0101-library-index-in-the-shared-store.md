# ADR-101: The library index lives in the shared store

- **Status:** Accepted
- **Date:** 2026-08-29
- **Supersedes:** [ADR-100](0100-project-tree-link.md) §3 and its Non-goals
  clause about `index.db`
- **Context:** fleet storage ruling, 2026-08-29

## Context

ADR-100 §3 put a Zotero-style index at `~/.scitex/scholar/library/index.db`
and made "read that file directly" the contract for downstream consumers —
scitex-writer's scholar bridge in particular — so that reading the library
required no Python dependency on scitex-scholar.

The fleet has since ruled that packages keep their state in the per-host
PostgreSQL, reached through the shared primitive `scitex_dev.store`, and that
no package hand-rolls its own database layer. scitex-scholar is in scope for
that ruling.

The two positions are not reconcilable by a compromise: an index file that
downstream tools open with their own driver is precisely the shape the ruling
forbids.

## Decision

The library index moves to the shared store, table `scholar_library_index`.

- `host_store()` resolves WHERE. Nothing in scholar derives a filesystem
  location for the index, and `<library_root>/index.db` is no longer written
  or read.
- `library_root` is part of the record IDENTITY, alongside `paper_id`. One
  store serves every library on the host, so two roots holding the same
  `paper_id` are two rows rather than a silent overwrite.
- A paper that disappears from `MASTER/` has its row HIDDEN, not deleted. The
  store has no delete verb, and a later rebuild un-hides it.
- `library db migrate` is removed. It existed to version a schema inside an
  index file; the store owns schema declaration.

The same move applies to the JCR impact-factor table
(`scholar_impact_factor`), for the same reason.

## Consequences

- **ADR-100's "filesystem + (optionally) `index.db`" API is now "filesystem".**
  `MASTER/<paper_id>/metadata.json` remains the authoritative, stable,
  additive-only contract, and it is still readable with no dependency on
  scitex-scholar. That half of ADR-100 is untouched and is what consumers
  should build on.
- **A consumer that opened `index.db` directly must change.** The index is a
  derived cache — every field in it comes from `metadata.json` — so a consumer
  can re-derive it by walking `MASTER/`, or read the store. No data is lost by
  the move; only the access path changes.
- **The index now needs a reachable store.** Previously a rebuild worked on any
  machine with a filesystem. This is the intended trade: a host whose store is
  down fails loudly rather than writing to a private local file that shares
  nothing.
- **CI cannot exercise the store half.** This project's tests run on
  GitHub-hosted runners, which cannot reach the fleet PostgreSQL. The index's
  derivation logic — identifier normalisation, duplicate-DOI detection, field
  extraction, ordering — is pure and fully covered by
  `tests/scitex_scholar/storage/test__library_index.py`; the round-trip through
  the store is verified by hand against a live store. This is a gap, and it is
  recorded here rather than hidden behind a skip that always skips.

## Non-goals

- Scholar still does not provide a Python SDK for consumers. The filesystem is
  the API.
- Scholar does not replicate or export the index for consumers that cannot
  reach the store; walking `MASTER/` is the supported fallback.
