# Changelog

All notable changes to `scitex-scholar` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.2] - 2026-07-12

### Fixed
- `verify-cites`: a bare `eprint` (no `doi`) BibTeX/BibLaTeX field --
  what arXiv's own "export citation" produces -- was checked only as a
  boolean gate, then discarded, falling through to a keyword-based
  title search that could non-deterministically miss the real paper
  and cascade to an unreliable CrossRef title-search fallback (verified
  in one run, unverified in another). `eprint` is now canonicalized to
  an arXiv DOI and routed through the deterministic `id_list` lookup.
- `verify-cites`: `VERIFIED` now requires the resolution to have gone
  through a real identifier (doi/arxiv-id/corpus_id), never a bare
  title match, no matter how high the title-similarity score.
  CrossRef/OpenAlex's title index is not guaranteed stable across
  identical queries, so a title/author/year fuzzy match (reachable by
  any identifier-less citation) is not deterministic evidence.
  `ResolvedRef` gained `identifier_based: bool`; a title-only match now
  caps at `UNVERIFIED` with a provenance note explaining why.

## [1.5.1] - 2026-07-12

### Fixed
- `ArXivEngine._search_by_doi` queried arXiv's API with the wrong field
  (`search_query=id:"..."`, a free-text search that silently returns
  zero entries for exact-ID lookups) instead of `id_list` (arXiv's
  documented direct-fetch parameter). Every DOI-form arXiv citation --
  the single most common citation form in ML/CS manuscripts -- fell
  through to the not-found fallback and could never classify VERIFIED
  in `verify-cites`, independent of the 1.5.0 `_std()` fix. Live-verified:
  a real arXiv DOI and a bare eprint id both now classify VERIFIED.
- `scitex_scholar.gui.launch()` crashed on startup with
  `KeyError: 'scholar_dir'` -- `PathManager.dirs` never had that key; the
  scholar root is exposed as the direct attribute `path_manager.scholar_dir`.
  The Scholar GUI (Flask app for browsing/managing the paper library) is
  reachable again.

## [1.5.0] - 2026-07-12

### Added
- `verify-cites`: resolve every `\cite` key in a manuscript to a real
  source (CrossRef/OpenAlex/ArXiv/SemanticScholar) and gate on the
  result. Classifies each citation as verified / unverified / stub /
  hallucinated / unlinked. Available as
  `from scitex_scholar.verify_cites import verify_cites, compute_exit_code`
  and `python -m scitex_scholar.verify_cites <manuscript_dir> [options]`
  (not yet wired into the `scitex-scholar` CLI group, pending a
  `_cli_main.py` file-size-gate refactor).
- `verify-cites --emit-clew` now saves a clew-ingestible
  `citations/v1` sidecar (`{"schema": "scitex-clew/citations/v1", ...}`)
  via `stx.io.save` instead of importing/calling `scitex_clew` directly,
  keeping scholar clew-agnostic per the ecosystem's acyclic-deps
  decision (2026-07-02).

### Fixed
- `verify-cites`'s resolver (`_std()`) read the wrong metadata dict
  shape (flat `title`/`doi` instead of the real engines' nested
  `basic.title`/`id.doi`), so it could never classify a citation as
  VERIFIED via any online path -- every real, correctly-cited paper
  silently degraded to UNVERIFIED. Fixed, with a guard so a
  not-found title-search echo (CrossRef/OpenAlex/ArXiv's
  `_create_minimal_metadata` fallback) cannot self-match into a false
  VERIFIED. Live-verified against a real DOI (now resolves VERIFIED)
  and a fabricated title (still resolves to no hit).
- `ScholarAuthManager` no longer hard-fails with `AuthenticationError`
  when no institutional auth provider is configured -- open-access
  paper fetches (arXiv, etc.) now proceed anonymously instead of
  blocking every browser-based download behind an OpenAthens/EZProxy/
  Shibboleth login nobody set up.
- Journal-name sanitization in `update_symlink()` no longer crashes
  with `AttributeError` (`path_manager._sanitize_filename` was never a
  real method) -- `paper fetch --project <name>` now actually creates
  the project symlink for papers with a journal name, instead of
  silently reporting success while skipping the link.

## [1.4.4] - 2026-07-11

### Fixed
- `ensure_workspace` is now exported at the package top level
  (`from scitex_scholar import ensure_workspace`). Previously missing from
  `__all__`/the lazy-import map, so the name silently resolved to the
  submodule instead of the function, breaking any caller expecting a
  callable (scitex-hub prod incident: scitex-template's
  `clone_scitex_minimal` -> `TypeError: 'module' object is not callable`).
- Search result `title`/`abstract` fields are now sanitized of raw
  JATS/HTML markup (`<jats:p>`, `<scp>...</scp>`, `<jats:title>`, ...) at
  `standardize_metadata()`, the single choke point every metadata engine
  (CrossRef, CrossRefLocal, OpenAlex, PubMed, Semantic Scholar, arXiv, ...)
  funnels through. Previously these tags leaked into consumer UIs
  (reported by the scitex-hub webapp).

## [1.4.1] - 2026-05-27

### Fixed
- `scitex-dev ecosystem audit-all` is now fully clean (0 errors, 0 warnings).
  - **MCP §6**: declared `[tool.scitex_dev] mcp_parity_exempt` — scitex-scholar
    is a service/workflow package whose MCP tool surface intentionally differs
    from its pure-function public API.
  - **PA-305**: moved type-hint-only `playwright.async_api` imports (728
    modules, incl. ~708 Zotero-style translators) under `if TYPE_CHECKING:`;
    added `capture_debug_artifacts_async` to the 16 modules that genuinely
    drive a browser (auth/browser infra + translator demos).

### Changed
- Require `scitex-browser>=0.1.15` (first release exporting
  `capture_debug_artifacts_async`).

## [1.4.0] - 2026-05-09

### Added — Library workflow

- **`library refresh [PROJECT] [--sync HOST]`** — one-button maintenance
  umbrella: reconcile `container.projects` ↔ filesystem symlinks, then
  regenerate every readable name (`PDF-NN_CC-..._IF-..._...`) via the
  canonical `LibraryManager.update_symlink`, then optional rsync push
  to one or more remote hosts. Each refresh + sync is recorded in
  `library/<project>/info/project_metadata.json`. Subsumes the
  previous `reconcile-projects` and `refresh-symlinks` standalone
  commands (removed; helpers remain as Python API).

- **`library list [PROJECT]`** — positional project arg auto-enables
  per-paper detail (still configurable via `-v` / `-vv` / `-vvv`).

- **`library bind PROJECT PROJECT-DIR`** — single-symlink view of the
  home library inside a project repo
  (`<project-dir>/.scitex/scholar/library/<project>` → `~/.scitex/scholar/library/<project>`).
  No data movement, no MASTER passthrough. `--unbind` removes the
  symlink. Verbless shorthand `library <project> <project-dir>`
  triggers when `<project>` already exists in home.

- **`library sync HOST [--remote-path PATH] [--pull] [--delete]`** —
  rsync the library to/from a remote host. `--remote-path` overrides
  the default `.scitex/scholar/library/[<project>/]`; `--copy-links`
  (default) follows symlinks for self-contained remote dirs.

- **`library export PROJECT --format <bibtex|tarball|flat-pdfs|zotero>`** —
  portable export. Default location:
  `~/.scitex/scholar/exports/<project>-<ts>.<ext>` (or under
  `<project-dir>/.scitex/scholar/exports/` when bound).

- **`library audit-files [--project P] [--no-rehash]`** — verify
  recorded files against disk: missing / orphan / hash_mismatch.
  Reads the new `metadata.path.files` registry (role + sha256 + size +
  added_at + source) populated by `paper fetch --pdf-*`.

- **`library zotero {import, export, diff}`** — bidirectional Zotero
  migration scaffold (engine in `integration/zotero/local_migrator.py`
  was already present; CLI verbs landed). **Marked as future work**
  — verify on a real round-trip before relying on it; tracked in
  `GITIGNORED/TODO.md`.

- **Categorized `--help`** at top level (`[Workflow] / [Dev]`) and on
  the `library` group (`[Daily] / [Layout] / [Share] / [Database]`),
  via a private `_CategorizedGroup` Click subclass.

### Added — Paper fetch (manual PDF import)

- **`paper fetch --pdf-main <path>`** (back-compat alias `--pdf`) —
  skip the browser/download stack and consume a user-provided main
  PDF. Metadata enrichment from `--doi`/`--title` still runs.
- **`paper fetch --pdf-supple <path>` (repeatable)** — supplementary
  files placed at `MASTER/<id>/supple-<original_name>`.
- **`paper fetch --attachment <path>` (repeatable)** — attachments
  placed at `MASTER/<id>/additional-<original_name>`.
- **`--doi` accepts URL form** — `https://doi.org/...`,
  `http://dx.doi.org/...`, `doi:10.x/y` all normalize.
- **DOI auto-extraction from PDF page-1** when `--pdf-main` is given
  without `--doi`/`--title`.
- **DOI mismatch warning** — after a `--pdf-main` import the page-1
  DOI is checked against `metadata.id.doi`; mismatch is logged
  loudly. Catches the kind of file-swap that crossed Maturana 2020 ↔
  Karoly 2019 last session.
- **Main PDF immutability** — `_step_07_import_files` `chmod 444`s
  the main PDF on import (Zotero-style: canonical record-of-paper
  stays read-only; annotated copies live alongside). Recorded as
  `"immutable": true` in `metadata.path.files`.

### Added — Browser-watch import (`library open-urls --watch`)

(The browser-side improvements landed across this session — listed
here for completeness; underlying engine already merged.)

- Tab-origin matching: every tab's `paper_id` is cached so a download
  from a known tab maps to the right paper without filename guessing.
- Popup tab inheritance via `Page.opener()` (publisher download
  buttons that spawn a new tab now carry the parent's paper_id).
- Dual watch dirs: Playwright's intercepted dir
  (`~/.scitex/scholar/cache/chrome/playwright_downloads/<session>/`)
  AND `~/Downloads`, so WSL→Windows mounts that block inotify don't
  prevent detection.
- SSO cookie injection: `~/.scitex/scholar/cache/auth/<provider>.json`
  is loaded and injected into the Playwright context before
  navigation, so paywalled URLs hit the authenticated session.
- Live event pump via `page.wait_for_timeout(1000)` (sync Playwright
  needed an explicit pump; events were arriving only on browser
  close).
- Colored output via `scitex-logging`; debug log file at
  `~/.scitex/scholar/cache/debug/watch_sessions/<session>/session.log`.
- Human-readable labels (`Smith 2020 Scientific Reports`) instead of
  paper-ids in user-facing log lines.

### Fixed

- **`.github/workflows/publish-pypi.yml`** — workflow YAML was
  malformed (duplicate keys + `needs: build` referencing a
  non-existent `build` job), so every push to `develop` triggered a
  zero-second failed run. Restructured into three sequenced jobs
  (`build` → `publish` → `release`) with consistent `inputs.version
  || github.ref` resolution; `release` job tolerates re-runs via
  `gh release create … || gh release upload --clobber`.
- **`_step_01_normalize_as_doi`** — accept `doi:`/`https://doi.org/`/
  `http://dx.doi.org/`/`https://www.doi.org/` URL forms; trim
  query/fragment.

### Internal

- New `metadata.path.files` registry (list of
  `{role, name, sha256, size, added_at, source, immutable}` entries)
  is the source of truth for `library audit-files`. Legacy
  `metadata.path.{pdfs, supplementary_files, additional_files}` are
  kept in sync for back-compat readers.

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
