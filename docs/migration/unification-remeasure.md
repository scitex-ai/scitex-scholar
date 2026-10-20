# Old-direct unification re-measure (U8) — 2026-10-20

Hub measured at `scitex-hub@cc53213` (`apps/workspace/scholar_app`),
leaf at the U1–U7 stack tip. Counts: hub 125 routes + 28 model classes
+ 24 migration files; leaf 34 flat routes.

## Unified by this program (leaf PRs #237–#247, U1–U7 #252–#258)

Search grid, range filters, header tools, library annotations (sidecar),
BibTeX import preview, graph multi-seed/query builds, CSV export,
single-paper citation, saved graphs, library remove + graph rename,
OA PDF download, syntax-help endpoint + `?` affordance, queue-status
chrome, source persistence (user-root JSON), selected RIS/EndNote,
graph step zoom, graph PNG download, node detail sheet (role/shape).

## Hub deletion ledger (Apps lane, AFTER leaf merges + dev-verified)

- [ ] U1: `urls/search.py` `api/search/syntax/` path + `views/search/api_syntax_help.py`
- [ ] U2: `templates/scholar_app/search_partials/progressive_loading.html`
      (verified unreferenced repo-wide)
- [ ] U3: `save_source_preferences` path in `urls/search.py` ONLY
      (`get/save_user_preferences` stay -- UserPreference model-backed)
- [ ] U4: `export_bulk_citations` path in `urls/library.py` + view in
      `views/export/views.py` (single-paper `get_citation` stays)
- [ ] U5: zoomIn/zoomOut button markup in `graph_stage.html` ONLY
- [ ] U6: downloadPngBtn markup in `graph_stage.html` ONLY
- [ ] U7: graphNodeSheet div + sheet hooks in `graph_stage.html`
- [ ] Final: re-grep all seven + legacy route count vs 122 baseline.

## Portable remainder (not in U-scope, tracked separately)

- 4 search engines hub serves that leaf lacks: bioRxiv/DOAJ/PLOS/PMC
  (card `scholar-search-engines-biorxiv-doaj-plos-pmc-20261019`, upstream
  APIs verified reachable; one engine per PR after the stack merges).

## Apps-owned remainder (filed on `scholar-leaf-parity-for-hub-model-drop-20261011`)

API keys + usage stats; trends/reco/analytics; collab groups,
collections, votes, repository DRF; PDF serve/store + pipeline;
bibtex enrichment jobs (~13 `bibtex_*` routes); per-source compat
shims (crossref proxy, `api/v1/scholar/*`); scitex-search gateway;
landing chrome; Annotation Reply/Vote/Tag (sidecar unified in slice 4).
Hub-side 26-model drop itself stays Apps-owned, not started.
