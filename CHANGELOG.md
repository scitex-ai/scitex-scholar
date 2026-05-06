# Changelog

All notable changes to `scitex-scholar` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2026-05-06

### Added
- **`scitex_scholar._mcp_server`** — FastMCP server exposing every handler in
  `_mcp.all_handlers` as a `scholar_<verb>_<noun>` MCP tool, plus the per-§5
  required `scholar_skills_list` / `scholar_skills_get` introspection tools.
  Discoverable as `scitex_scholar._mcp_server.mcp` by `scitex-dev ecosystem
  audit-mcp-tools`. Replaces the legacy `scitex_scholar.mcp_server` (still
  shipped, deprecation-warning-only).

### Fixed (skills audit clearance)
- **§1d vocabulary**: `lookup` moved from `nouns` to `transitive_verbs` in
  `.scitex/dev/cli-audit-dict.yaml` (was `verbs`, which is not a key the
  auditor recognises). `library db lookup` now passes §1d.
- **§2 read-verb `--json`**: added `--json` flag to `skills get`.
- **§11 argparse residue**: replaced the only remaining `argparse.Namespace`
  use in `_cli_main.py` with `types.SimpleNamespace` (compat shim for
  `pdf_highlight._cli.run` which still takes a Namespace-shaped object).
- **SK109**: renumbered skill leaves so `05_mcp-tools.md` exists at the
  expected slot (was `09_mcp-tools.md`); `api-overview` shifted to `06`.
- **PS204**: extracted Click app from `__main__.py` to `_cli_main.py` so the
  test mirror `tests/scitex_scholar/test__cli_main.py` resolves to a unique
  src file (was: 3 `__main__.py` files share basename, regex blind spot).
  `__main__.py` is now a thin shim.

### Known (architectural divergence — won't fix)
- audit-mcp-tools §6 reports 12 Python APIs without MCP-tool matches and 24
  MCP tools without Python-API matches. The two surfaces are deliberately
  different shapes: the Python API exposes facade classes (`Scholar`,
  `Paper`, `Papers`, `ScholarConfig`), the MCP API exposes per-operation
  tools (`scholar_search_papers`, `scholar_resolve_dois`, …). Aligning them
  would require collapsing the API or fragmenting the MCP surface — neither
  is desirable.

## [1.3.0] - 2026-05-06

### BREAKING — CLI noun-verb grammar refactor

The CLI top-level commands have been regrouped under noun-verb groups to comply
with the SciTeX subcommand grammar standard
(`~/.claude/skills/scitex/general/03_interface_02_cli/02_subcommand-structure-noun-verb.md`).

The pre-1.3.0 top-level forms still work but emit a one-line `DeprecationWarning`
on stderr and will be **removed in 1.4.0**.

#### Migration

| Old (deprecated, emits DeprecationWarning) | New (1.3.0+)                                 |
|--------------------------------------------|----------------------------------------------|
| `scitex-scholar single …`                  | `scitex-scholar paper fetch …`               |
| `scitex-scholar parallel …`                | `scitex-scholar paper fetch-batch …`         |
| `scitex-scholar bibtex --bibtex …`         | `scitex-scholar bibtex import --bibtex …`    |
| `scitex-scholar highlight …`               | `scitex-scholar pdf highlight …`             |
| `scitex-scholar link-project-tree …`       | `scitex-scholar library link-project-tree …` |
| `scitex-scholar materialize …`             | `scitex-scholar library materialize …`       |
| `scitex-scholar dematerialize …`           | `scitex-scholar library dematerialize …`     |
| `scitex-scholar db {build,migrate,lookup,list,audit}` | `scitex-scholar library db {build,migrate,lookup,list,audit}` |
| `scitex-scholar mcp {start,list-tools,doctor,install}` | _(unchanged — already noun-verb)_ |

Old and new forms route to the same handler, so behaviour is identical.

### Added (CLI ecosystem compliance)

- **Click migration** — CLI rewritten in Click (was: argparse). Matches the canonical SciTeX framework; unlocks shared infrastructure (`--help-recursive`, ecosystem-wide `--json`).
- **Cold-start latency** — `import scitex_scholar` is now ~64ms (was 4.5s) via PEP 562 lazy `__getattr__` in `__init__.py`. Tab-completion latency drops by ~70×.
- **Universal flags at top level**: `-V/--version`, `--help-recursive`, `--json`.
- **New top-level commands**:
  - `list-python-apis` — print public callables in `scitex_scholar.__all__`.
  - `skills {list, get, install}` — list / read / install bundled skill leaves.
- **Per-leaf flags**:
  - Mutating verbs (`paper fetch`, `paper fetch-batch`, `bibtex import`, `pdf highlight`, `library link-project-tree`, `library materialize`, `library dematerialize`, `library db build`, `mcp start`, `mcp install`): `--dry-run`, `--yes/-y`.
  - Read verbs (`mcp list-tools`, `library db list`, `library db lookup`, `library db audit`, `skills list`, `list-python-apis`): `--json`.
  - Every leaf has a concrete `Example:` block in `--help`.
- `.scitex/dev/cli-audit-dict.yaml` — vocabulary entries for `bibtex`, `pdf`, `lookup`, `dedupe`.

### Fixed

- **PS102** — Removed orphan visible `./scitex/` directory at repo root (held a stale `clew.db`; the live state lives in hidden `.scitex/`).
- **PS204** — Renamed `tests/scitex_scholar/cli/test_noun_verb_grammar.py` → `tests/scitex_scholar/cli/test___main__.py` to mirror its src file.

## [1.2.4] - 2026-05-06

### Fixed
- **CLI no-args UX**: `scitex-scholar` (no subcommand) now prints help and exits 0
  instead of `error: the following arguments are required: command` (exit 2).
- **CLI prog name**: was `python -m scitex.scholar` (legacy/wrong namespace);
  now `scitex-scholar`, matching the installed entry point.
- **Sphinx strict build**: 38 warnings → 0. Adds previously-unlinked toctree
  entries (`api/index`, `cli`, `mcp`, `quickstart`, `semantic_highlight`),
  fixes Numpy-style docstring formatting in `Papers.filter`, `Papers.sort_by`,
  `Scholar.__init__`, `apply_filters`, `ScholarConfig.__dir__/__getattr__`.
- **`.readthedocs.yaml`**: `fail_on_warning: false` → `true` to prevent regression.

### Added
- **CLI `scitex-scholar mcp list-tools`**: print the MCP tool names this package
  registers (`scholar_*`) without starting the server. Introspection helper.

### Changed (community-project compliance)
- Drop `__email__` from `scitex_scholar.__init__`; scrub `ywatanabe@scitex.ai`
  from package-shipped READMEs and the BibTeX export comment header (CLA legal
  block in `CLA.md` retained).
- README skill links now point at the published RTD pages instead of internal
  `src/scitex_scholar/_skills/...` paths that don't resolve for pip-installed
  users.
- README CLI examples standardized on `scitex-scholar <subcommand>` form.
- Drop duplicate skill leaves under `_skills/scitex-scholar/`: merged
  `06_quick-start.md`, `07_python-api.md`, `08_cli-reference.md` content into
  the canonical `02/03/04` leaves.
- `_skills/scitex-scholar/05_api-overview.md`: drop redundant `scitex-scholar`
  tag (slug-form-only per SK710).

## [1.2.1] - 2026-04-21

### Fixed

- **`db build` no longer raises `sqlite3.IntegrityError: UNIQUE constraint failed: papers.doi` when multiple MASTER entries have `doi=""` (empty string).** The `UNIQUE(doi) WHERE doi IS NOT NULL` index treats NULL as distinct per row, but empty string is a real value and multiple of them collided. `_row_from_metadata` now normalizes empty and whitespace-only DOI / arxiv_id / pmid to `None` before insert, matching the semantic intent ("no ID"). Regression test added.

## [1.2.0] - 2026-04-21

### Added

- **CLI `db dedupe`** — resolve duplicate-DOI entries in MASTER. Scores candidates by a reproducible rubric (`+10` PDF, `+1` per populated `basic.*` field, `+1` per populated `id.*` field, `+log(1+citation_count)` capped at 5, `mtime` tiebreaker). Losers move to `MASTER_quarantine/<paper_id>/` by default (reversible) or can be `--hard-delete`d. Dry-run by default; `--apply` executes. Output shows per-group scores so users see *why* each winner was picked. Idempotent on re-run. Completes the audit → dedupe → build workflow surfaced by issue #12. (PR #15)

## [1.1.2] - 2026-04-21

### Fixed

- **Atomic `metadata.json` / `tables.json` writes** (`PaperIO.save_metadata`, `PaperIO.save_tables`). Previous implementation was a plain `open("w") + json.dump`, which left behind truncated files if the process was killed mid-write. One such victim (paper_id `3DD203D4`) was surfaced by `db audit`. New implementation writes to a `.tmp` sibling, `flush` + `fsync`, then `os.replace`s into place — readers always see either the previous valid JSON or the new valid JSON, never a half-written file. 8 unit tests cover roundtrip, overwrite, mid-write crash simulation, and cleanup-on-failure.

## [1.1.1] - 2026-04-21

### Added

- **CLI `db audit`** — read-only library anomaly report (closes #12). Walks `MASTER/` and decorated symlinks, reporting duplicate DOIs, unparseable `metadata.json`, missing/unreferenced PDFs, missing DOIs (informational), and orphaned decorated symlinks. Human-readable by default; `--json` for tooling. Exits `0` always unless `--strict` is passed. Pure filesystem read; no DB writes. Unblocks users whose `db build` raises on duplicate DOIs — they can audit first, fix, then rebuild.

## [1.1.0] - 2026-04-21

### Added

- **CLI `link-project-tree <dir>`** — creates `<dir>/.scitex/scholar/library → ~/.scitex/scholar/library/` as an idempotent absolute symlink. `--force` replaces a differing target. See [ADR-100](docs/architecture/ADR-100-project-tree-link.md). (PR #4)
- **CLI `materialize <link_path> --bib <bib>`** — replaces a library-symlink with a real directory containing only the `MASTER/<paper_id>/` subtrees for DOIs cited in `<bib>`. Useful for tarball handoff. (PR #5)
- **CLI `dematerialize <path> [--target <dir>]`** — inverse of `materialize`: deletes the real directory and replaces it with a symlink to `~/.scitex/scholar/library` (or `--target`). (PR #5)
- **CLI `db {build, migrate, lookup, list}`** — Zotero-style SQLite index at `<library_root>/index.db` for fast paper lookup. Schema v1 exposes `paper_id, doi, arxiv_id, pmid, title, year, venue, is_oa, authors_json, abstract, citation_count, updated_at`. Consumers read the DB directly with sqlite3 — no Python dependency on `scitex-scholar`. (PR #6)
- **ADR-100** documenting the project-tree link + materialize lifecycle (filesystem-as-API contract, additive-only `metadata.json` schema, `MASTER/<paper_id>/` layout). (PR #4)
- `[tool.pyright]` configuration in `pyproject.toml` with `typeCheckingMode = basic`, targeted excludes, and justified rule suppressions for the false-alert-dominated categories on this codebase. (PR #8)
- `Part of SciTeX` / Four Freedoms footer to README.

### Changed

- `library-index-db` (PR #6): `build()` now **fails loudly** on duplicate DOIs in MASTER instead of silently overwriting (the previous `INSERT OR REPLACE` masked library corruption).
- `library-index-db` (PR #6): `build()` now writes to a temp file and atomically swaps, so a failed rebuild preserves the existing DB.
- Repo-wide ruff cleanup: 806 → 0 errors. 27 real bugs fixed (missing `import re` in `dpla.py`; classmethod `self.` → `cls.__name__` in `registry.py`; `TYPE_CHECKING` imports for `Paper`/`Papers`/`OAResult`; duplicate dict key in `OpenAlexEngine`; redefined functions in `manual_download_utils`; `type() ==` → `type() is` in `_CascadeConfig`; etc.). (PR #7)
- Repo-wide pyright cleanup: 1,577 → 0 errors with `basic` mode + real fixes across 49 files. (PR #8)

### Fixed

- `core/_mixins/_savers.py`: broken relative import `..storage` → `...storage` (would have raised `ImportError` at module load on any live path). (PR #8)
- `core/Papers.py`: bibtex parsing body incorrectly nested inside an `if "year" in fields:` guard — restored correct flow. (PR #8)

### Removed

- Dead ZenRows proxy code path — `use_zenrows_proxy` was a threaded constructor parameter that never evaluated truthy; import of a non-existent `browser/remote/ZenRowsProxyManager` module lived behind the `if` branch. Removed the parameter from `ScholarBrowserManager.__init__` and its two CLI call sites.
- Broken `impact_factor/estimation/` subtree — imported a non-existent `fetchers` module; `ImpactFactorCalculator` was unreachable in practice. The live `impact_factor/ImpactFactorEngine.py` and `impact_factor/jcr/` are unaffected.
- Hidden `metadata_engines/.combined-SemanticScholarSource/` backup directory.

[1.1.0]: https://github.com/ywatanabe1989/scitex-scholar/compare/v1.0.1...v1.1.0
