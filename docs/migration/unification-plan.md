#!/usr/bin/env markdown
# Old-direct → leaf unification plan

**Goal:** one Scholar GUI — the leaf `scitex_scholar._django` (latest scitex-sdk) —
carrying every old-direct behavior worth keeping; then the hub `scholar_app`
old-direct routes/templates are deleted. Operator directive 2026-10-20:
work the steps one by one until told to stop.

**Standing rules:** implement CLEAN on the leaf, never port hub dirt; one-way
dependency (all logic in scitex-scholar, hub only knows the plugin contract);
leaf stays off hub DB; no Django models leaf-side; flat urlconf only
(`test_urls.py` — hub gates each `URLPattern.callback` with login); one
assertion per test (STX-TQ007, tuple compares); test files mirror a src module
name (PS-204); run `tests/develop/test_audit.py` locally before PRs; contract
venv `/uvwork/venv-agent`, `-p no:cacheprovider`.

**Done (merged):** unification slices 1–11 (PRs #237–#247) → release v1.18.0
(PR #249) → main (PR #250). Parent card
`scholar-old-direct-leaf-migration-20261019` is done.

## Step order (tab/section order; each step = leaf PR, then hub deletion PR)

| Step | Leaf build | Hub deletion (Apps, AFTER leaf merge + dev-verify) |
|------|-----------|-----------------------------------------------------|
| U1 | `GET api/search/syntax-help` static JSON mirroring hub `api_search_syntax_help` + `?` affordance in Search header | delete `urls/search.py` syntax path + `views/search/api_syntax_help.py` |
| U2 | bind existing pipeline `on_progress` to queue-status chrome (hidden until a run) | delete `search_partials/progressive_loading.html` (verify unreferenced first) |
| U3 | source-selection persistence: visitor `localStorage` + file-user user-root JSON (no `UserPreference` model); `?sources=` echo unchanged | delete `save_source_preferences` path only (`get/save_user_preferences` stay — model-backed, Apps-owned) |
| U4 | bulk citations RIS/EndNote over selected (extend BibTeX-only Blob path with leaf ris/endnote formatters) | delete `export_bulk_citations` path + view (single-paper `get_citation` stays — 501 stub) |
| U5 | graph step zoom-in/out on existing renderer transform | delete zoom button markup from `graph_stage.html` only (shell + fit/download/sheet stay) |
| U6 | graph download-PNG client-side (canvas/SVG serialize, no backend) | delete download button markup from `graph_stage.html` only |
| U7 | graph node detail sheet from loaded `graph_data` metadata, no new endpoint | delete node-sheet div + hooks from `graph_stage.html` |
| U8 | route-by-route hub-vs-leaf diff; confirm zero portable remainder; file Apps-owned remainder (API keys, trends/reco/analytics, collab groups/collections/votes, repository, PDF serve/store, bibtex jobs, per-source compat shims, scitex-search gateway, landing chrome, ASTA) on `scholar-leaf-parity-for-hub-model-drop-20261011` | ledger: confirm all U1–U7 deletions landed (re-grep each path) + final legacy-route count vs 122 baseline |

**Per-step VERIFY:** pins RED-first; download round-trips per format (U4);
screenshot zoom steps (U5); non-blank PNG (U6); click-node sheet with
title/meta + focus return (U7); exported diff doc attached as comment (U8).

**Boundaries:** hub-side deletions and the 26-model drop are Apps-owned;
leaf agent prepares exact deletion specs, never pushes hub branches. SDK
releases (e.g. tabs polish #60 pickup) are SDK-owner lane.
