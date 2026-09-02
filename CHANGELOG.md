# Changelog

All notable changes to `scitex-scholar` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.10.0] - 2026-09-02

MINOR, not patch. This release removes public API (`CitationGraphBuilder(db_path=)`,
`library db migrate`), renames a CLI option (`--db-path` → `--api-url`) and two
`/api/health` fields, moves the Django ORM to PostgreSQL, and flips the
`DJANGO_DEBUG` default. None of that belongs in a patch. It follows this repo's
precedent of shipping breaking surface changes in minors (the Flask→Django GUI
went 1.7.x → 1.9.0); a strict reading would call it 2.0.0, and that reading was
considered and not taken.

### Security
- **`DJANGO_DEBUG` now defaults to `"false"`** (#137). It defaulted to `"true"`,
  which selected `ALLOWED_HOSTS="*"` on an app with no authentication for any
  `gui serve` that forgot the env var. Flipping the default alone would have
  reintroduced the 400 that #126 fixed for `--host 0.0.0.0` — a bind-all server
  receives real interface addresses in the Host header, and `0.0.0.0` never
  matches them — so `--host 0.0.0.0` now contributes this machine's hostname
  and every interface IPv4 (read from the interfaces via `SIOCGIFADDR`, not from
  name resolution, which resolved to the wrong address inside a container).
  Standalone `/static/` is served through the staticfiles finders regardless of
  `DEBUG`; `urls.py` (what hub mounts) is untouched. Verified live on three
  arms; the interface-enumeration test derives its expected address by an
  independent method so it is not the implementation checking itself.

### Added
- **`/api/health` reports `version`** (#132), so "is this deployment running
  what we shipped?" is answerable over HTTP. Scholar served no version anywhere
  before; scraping the page for one produced a false positive off a CDN URL
  (`highlight.js/11.9.0`). Caveat carried in the docstring: the value comes from
  `importlib.metadata`, which is frozen at install time, so it is trustworthy for
  a deployed wheel and not for an editable dev checkout.
- **Tests now guard the urlconf shape hub authenticates** (#129): every entry
  must be a flat `URLPattern`, because hub gates the leaf by wrapping each
  callback in `login_required`, and a nested `include()` would publish its
  routes unauthenticated. Includes a positive control that builds an
  `include()` and asserts the predicate rejects it.

### Fixed
- **The local test run tests THIS checkout** (#130). `pythonpath = ["src"]` in
  pytest config plus a session-start guard that compares the imported module
  PATH (never `__version__`) against the checkout and aborts (exit 3) on a
  mismatch. Before this, a bare `pytest` imported whatever wheel the ambient
  interpreter held — an older wheel went red and exposed it; an equal-or-newer
  one would have gone green against code the branch did not contain. CI never
  saw it and cannot: it installs the branch.
- **`scitex-ui>=0.19.0`** (#131): the shared shell hardcoded `<html lang="en">`,
  which is where a screen reader takes its pronunciation rules. Scholar does not
  call `shell_context()`, so it depends on the template-level default; verified
  on a real response from the published wheels. Two stale prose claims deleted
  in the same change — one of them a pinned "verified against scitex_ui 0.17.0"
  that had been quoted as a measurement while 0.18.0 was installed.

### Changed
- **Scholar's own state moved off local database files and onto the shared
  store (`scitex_dev.store`).** Fleet ruling, 2026-08-29: storage is the
  per-host PostgreSQL, reached through the shared primitive.
  - The **library index** (`library db build/lookup/list`) no longer writes
    `<library_root>/index.db`. Rows live in the `scholar_library_index` table,
    keyed by `(library_root, paper_id)` so one store can serve every library on
    the host. Papers that disappear from `MASTER/` are HIDDEN rather than
    deleted, and a later rebuild un-hides them.
  - The **JCR impact-factor table** moved to `scholar_impact_factor`. This also
    fixes the lookup outright: `DEFAULT_DB` resolved to a path OUTSIDE the
    repository after the monorepo split, so every impact-factor lookup had been
    failing silently. `build_database.py` now loads a JCR Excel export into the
    store and stamps each row with the JCR edition it came from, instead of
    re-deriving the year from a filename at read time.
  - The **Django ORM** points at `scitex-primary:55432/scitex`, overridable per
    field via `SCITEX_SCHOLAR_DB_*`.
- **The citation graph talks to crossref-local over HTTP only.** Scholar no
  longer opens crossref-local's data files itself; the package that owns that
  corpus is the one that reads it. `CitationGraphBuilder(db_path=...)` is gone
  — pass `api_url=`, or leave it unset and let the endpoint be resolved from
  `SCITEX_SCHOLAR_CROSSREF_LOCAL_API_URL`. The GUI's `--db-path` option is now
  `--api-url`, and `/api/health` reports `api_available` / `api_url` in place
  of `db_available` / `db_path`.

### Removed
- **`library db migrate`.** It managed a schema version inside an index file.
  The store owns schema declaration, so there is nothing left for it to do.
- **`citation_graph/database.py`** and the local-file citation-graph mode.
- **`cli/_library_index.py`** — an orphaned second implementation of the `db`
  subcommands whose `register_subparser` was never called from anywhere.
- **`sql-manager` and `sqlalchemy` dependencies**, which existed only for the
  previous JCR backend. `scitex-dev` becomes a core dependency in their place.

### Fixed
- **`Scholar.enrich_papers()`'s impact-factor path was dead code.** It called
  `ImpactFactorEngine.enrich_papers()`, a method that has never existed; the
  resulting `AttributeError` was caught and logged as "JCR engine unavailable
  ... falling back to calculation method" — a fallback that does not exist
  either. It now enriches papers, mirroring the pipeline's implementation.

## [1.9.0] - 2026-08-23

### Added
- **`SCITEX_SCHOLAR_ALLOWED_HOSTS`** (comma-separated) for deployments the bind
  address alone does not cover -- a reverse proxy passing a DNS name, a MagicDNS
  name, several addresses at once.

### Changed
- **The Django UI renders inside scitex-ui's shared workspace shell.** scholar was
  the only leaf shipping its own `<html>` document; it now extends
  `scitex_ui/standalone_shell.html` like scitex-storage, scitex-writer and
  figrecipe, so it picks up the shared frame and theme. Block names were verified
  against the installed scitex-ui, not the source tree.
- The page title comes from `app_label`, which reads `SCITEX_APP_MODE`, so the
  browser tab alone distinguishes a hub-embedded instance from a standalone one.

### Fixed
- **Serving on any non-loopback address answered 400 to every request.**
  `ALLOWED_HOSTS` was a hardcoded loopback-only list with no way to extend it, so
  `gui serve --host <addr>` started cleanly, printed a correct-looking URL, and
  then rejected every caller with nothing in the banner to suggest why.
  `--host` now contributes its own address, and `ALLOWED_HOSTS` switches on
  `DEBUG` (operator ruling): `["*"]` in development, loopback plus the explicit
  list otherwise. ANY DEPLOYMENT MUST SET `DJANGO_DEBUG=false` -- the permissive
  branch is the default branch and this app has no authentication of its own.
- **A template comment rendered as visible text across the top of the UI.**
  Django strips `{# ... #}` only on a SINGLE line; a multi-line one is emitted
  verbatim, and this template had a six-line explanatory comment above the
  stx-mount marker. Now `{% comment %}`. Found by the operator looking at the
  running page -- no test caught it, because the suite asserted that the right
  things were PRESENT and nothing asserted that wrong things were ABSENT.
- The GitHub Release step of the release pipeline no longer depends on the
  self-hosted runner's `gh` CLI, which aborts on a machine-local config before it
  ever reads its token.

### Internal
- Two regression tests pin that no raw template syntax reaches the browser, the
  second acting as a control so the pair cannot pass by rendering nothing.

## [1.8.0] - 2026-08-23

### Added
- **The Django UI can be mounted under a path prefix.** Previously the app
  only worked at the site root: client code built root-absolute URLs
  (`/api/graph/...`) that 404 under any mount, and one call was
  prefix-*lucky* -- `fetch('api/search')` resolved correctly at `/scholar/`
  and broke at `/scholar`. The server now declares its mount point via
  scitex-app's `stx-mount` contract (`<meta name="stx-mount">`, fed by
  `mount_prefix(request)`), and every request joins it explicitly. Verified
  by booting the app at `/scholar/`, not by inspection (#113, #118).
- **Package search in the standalone GUI's Search tab** (#95).

### Changed
- **Design tokens come from scitex-ui instead of being shadowed locally.**
  Seven token definitions that silently overrode the shared theme were
  removed, so the app follows the ecosystem's light/dark palette (#115).
- The GUI adopts scitex-app's shared guarded launcher (#102), and the
  scitex-app dependency is now hard rather than silently optional (#111).

### Fixed
- **Every on-disk MCP handler raised `KeyError: 'scholar_dir'`.** Both
  scholar-directory helpers read `path_manager.dirs["scholar_dir"]`, a key
  that does not exist -- only the `.scholar_dir` attribute does. Nine call
  sites in `_mcp/handlers.py` and four in `mcp_server.py` failed before
  doing any work (#120).
- **An API key set exactly as the documentation instructs was ignored.**
  Scholar's own environment variables are now read under the documented
  `SCITEX_SCHOLAR_` prefix, with a deprecation warning on the legacy names
  (#109).
- **The app tile advertised version 0.1.0 while the package shipped 1.7.1.**
  The manifest declared a hand-written `version` that had drifted; it now
  derives from the installed distribution (#119).
- Importing a `_cli/*` group module first crashed on a cold interpreter --
  a `_cli/* <-> _cli_main` import cycle (#108).
- OA detection and journal normalization no longer crawl OpenAlex on the
  request hot path (#96, #97).
- `verify-cites` now requires a real identifier before classifying a
  citation VERIFIED; a title match alone was not enough (#81).
- The AGPL-3.0 "How to Apply" template text says **only**, matching the
  project's declared `AGPL-3.0-only` license (#66).

### Internal
- Test guards that were passing without testing anything: the import-graph
  guard parsed with `ast` instead of failing open (#114), and the design
  token guard now scans the template (where 11 tokens are used) and
  resolves `@import` instead of globbing a directory (#116, #117).

## [1.7.1] - 2026-07-14

### Fixed
- **Generated BibTeX files could be unparseable when a header comment contained
  a raw `@`.** BibTeX parsers locate entries by scanning for `@` and do not
  treat `%` as a comment introducer, so an `@` in a generated header line (an
  `@`-bearing source filename, an email address) was read as the start of a
  malformed entry and aborted the parse of an otherwise valid file. All writers
  now route their output through a single `sanitize_bibtex_comments()` choke
  point, which neutralizes `@` inside `%` lines while leaving entries and field
  values untouched.

### Changed
- `storage/BibTeXHandler.py` (previously 1155 lines) is split into mixins under
  `storage/_bibtex/` — parsing, writing, merging and project bibliographies —
  with `BibTeXHandler` as the thin composed class. Purely internal: the public
  import (`from scitex_scholar.storage import BibTeXHandler`) and the full method
  surface are unchanged.

## [1.7.0] - 2026-07-13

### Added
- **Top-level facade for the search internals that downstream consumers
  depend on.** `ScholarSearchEngine` and `SearchQueryParser` are now
  importable directly from the package root
  (`from scitex_scholar import ScholarSearchEngine, SearchQueryParser`),
  so consumers can migrate off deep-internal paths
  (`scitex_scholar.search_engines.ScholarSearchEngine`,
  `scitex_scholar.pipelines.SearchQueryParser`). The deep paths keep
  working unchanged. A new import-contract regression test
  (`tests/integration/test_hub_import_contract.py`) asserts both the deep
  paths and the facade resolve, so any future relocation of these symbols
  fails loudly in CI rather than silently degrading a downstream consumer
  (e.g. scitex-hub's scholar_app, which deep-imports these).

## [1.6.1] - 2026-07-13

### Fixed
- **GUI: the Alt+I / Ctrl+I element inspector now loads.** The Django
  migration installed `scitex_ui` as an optional app for the shared
  workspace-shell assets but never wired its
  `ElementInspectorMiddleware`, so the visual DOM-debugging overlay
  silently did nothing. The middleware is now appended to `MIDDLEWARE`
  whenever `scitex_ui` is importable, matching the existing guarded
  `INSTALLED_APPS` append.

## [1.6.0] - 2026-07-12

### Changed
- **GUI: migrated the standalone browser interface from Flask to Django**,
  following `scitex-writer`'s reference pattern (`scitex_app.run_standalone`
  for the standalone server, guarded optional `scitex_ui` import for the
  shared favicon convention). The `scholar gui {open,serve,status,stop}`
  CLI surface is unchanged; only the backend swapped. Port 31297 unchanged.
  The Flask dependency is removed entirely (`django>=4.2` +
  `scitex-app>=0.2.8` replace it in the `[server]` extra). This is a
  standalone-only change -- it does not touch or replace scitex-hub's
  separate, independently-versioned `scholar_app`.

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

- **`db build` no longer fails with a uniqueness violation on `papers.doi` when multiple MASTER entries have `doi=""` (empty string).** The unique-DOI constraint treated an absent DOI as distinct per row, but empty string is a real value and multiple of them collided. `_row_from_metadata` now normalizes empty and whitespace-only DOI / arxiv_id / pmid to `None` before insert, matching the semantic intent ("no ID"). Regression test added.

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

- **CLI `link-project-tree <dir>`** — creates `<dir>/.scitex/scholar/library → ~/.scitex/scholar/library/` as an idempotent absolute symlink. `--force` replaces a differing target. See [ADR-100](docs/adr/0100-project-tree-link.md). (PR #4)
- **CLI `materialize <link_path> --bib <bib>`** — replaces a library-symlink with a real directory containing only the `MASTER/<paper_id>/` subtrees for DOIs cited in `<bib>`. Useful for tarball handoff. (PR #5)
- **CLI `dematerialize <path> [--target <dir>]`** — inverse of `materialize`: deletes the real directory and replaces it with a symlink to `~/.scitex/scholar/library` (or `--target`). (PR #5)
- **CLI `db {build, migrate, lookup, list}`** — Zotero-style index at `<library_root>/index.db` for fast paper lookup. Schema v1 exposes `paper_id, doi, arxiv_id, pmid, title, year, venue, is_oa, authors_json, abstract, citation_count, updated_at`. Consumers read the index file directly — no Python dependency on `scitex-scholar`. (PR #6)
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

[1.1.0]: https://github.com/scitex-ai/scitex-scholar/compare/v1.0.1...v1.1.0
