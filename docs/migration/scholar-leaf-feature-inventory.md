# Scholar leaf migration inventory — first slice

This inventory treats `scitex-scholar` as the single source of truth for Scholar UI, search, readiness, fallback, preferences, results, Library, enrichment, and citation graph. The Hub remains the reference during migration and continues to own authentication, routing, project context, and deployment. The Hub reference is compared, not edited or deleted.

## Cited behavior inventory

| Behavior | Hub reference evidence | Leaf evidence at this slice | Status / preserved acceptance gate |
|---|---|---|---|
| App-local navigation and readiness | Hub renders BibTeX/Search/Graph tabs and per-source readiness LEDs (`apps/workspace/scholar_app/templates/scholar_app/scholar_base.html:38-99`). | Leaf renders Search/Library/Citation Graph tabs (`src/scitex_scholar/_django/templates/scholar/scholar.html:135-140`) and a service status surface (`:86-97`). | **Partial.** Preserve visible source-level readiness, retry/error states, and source controls before retiring the Hub reference. |
| Local-first sources with explicit controls | Hub labels Crossref Local and OpenAlex Local as fast/recommended, then separates slower external APIs (`apps/workspace/scholar_app/templates/scholar_app/search_partials/search_controls.html:114-190`). | Leaf package config now declares `CrossRefLocal` and `OpenAlexLocal` primary, with online `CrossRef` and `OpenAlex` fallback (`src/scitex_scholar/config/default.yaml`; `src/scitex_scholar/config/_categories/search_engines.yaml`). | **Policy pinned; UI incomplete.** Local corpus adapters remain owned by `crossref-local`/`openalex-local`; no Hub search logic is copied. Preserve per-source enablement, health, counts, and explicit fallback visibility. |
| High-volume result path | Hub defaults local search to 10,000 and caps aggregate results separately (`apps/workspace/scholar_app/views/search/config.py:24-27,102`); its search core returns up to 10,000 (`apps/workspace/scholar_app/views/search/search_core.py:212`). | Leaf GUI currently offers 10/20/50/100 results (`src/scitex_scholar/_django/templates/scholar/scholar.html:168-174`), while the package search facade accepts `max_results` (`src/scitex_scholar/search_engines/ScholarSearchEngine.py:94-110`). | **Not migrated.** Acceptance gate: demonstrate responsive 10k–20k result handling (streaming/virtualization or equivalent), stable sorting/filtering, cancellation, and bounded browser memory before parity is claimed. |
| Library | Hub unified surface includes a Library tab (`apps/workspace/scholar_app/templates/scholar_app/scholar_unified.html:78-104,296-351`). | Leaf has Library import/export/list/enrich UI (`src/scitex_scholar/_django/templates/scholar/scholar.html:251-313`) backed by package-owned endpoints. | **Partial.** Preserve project-scoped selection, save/remove, import/export, durable preferences, and large-library behavior. |
| Enrichment | Hub exposes BibTeX enrichment and names abstract, URL, citation count, and impact factor outputs (`apps/workspace/scholar_app/templates/scholar_app/bibtex_partials/enrich.html:5-39`). | Leaf keeps enrichment contextual to each Library item (`src/scitex_scholar/_django/templates/scholar/scholar.html:251-268`). | **Partial.** Preserve batch progress, retry/resume, source provenance, downloadable output, and project attachment. |
| Citation graph | Hub exposes citation graph navigation and service routes (`apps/workspace/scholar_app/templates/scholar_app/scholar_base.html:48-58`; `apps/workspace/scholar_app/services/citation_graph/service.py`). | Leaf ships the graph form, visualization, details, and related papers (`src/scitex_scholar/_django/templates/scholar/scholar.html:315-402`). | **Partial.** Preserve weighted graph construction, cache bypass, related-paper ranking, graph export, loading/error states, and local-corpus readiness. |
| Project context | Hub injects current project identity/config (`apps/workspace/scholar_app/templates/scholar_app/scholar_base.html:242-253`). | Leaf owns one canonical app header and one scitex-ui picker. The host advertises its provider; standalone serves `LocalProjectProvider`; selection navigates with `?project={id}`. | **Implemented in this slice.** Gate: exactly one picker, left of app actions, accessible provider only, current value retained, 390px full-width/44px shared control. |
| Mobile | Hub keeps a dedicated mobile Scholar E2E check (`tests/e2e/playwright/test_mobile_scholar.py:1-67`). | Leaf stacks search controls under 768px and adds a canonical wrapping header/picker contract at 600px (`src/scitex_scholar/_django/static/scholar/css/_partials/_layout.css:119-194`), covering 390px. | **Source-contract verified, not visual parity.** Preserve no horizontal overflow, tappable controls, readable results/Library/graph, and run a real 390px browser regression when the leaf test harness gains an authenticated browser fixture. |

## Slice acceptance gates

1. Scholar owns the app header markup and places the shared scitex-ui picker exactly once in the canonical left slot.
2. Mounted hosts supply `SCITEX_PROJECT_PROVIDER` / `SCITEX_PROJECT_PROVIDER_URL`; Scholar does not import Hub models or permission logic.
3. Standalone uses scitex-ui `LocalProjectProvider` and a package-owned listing endpoint.
4. A pick navigates to `?project={id}` and an explicit accessible project becomes current.
5. Both package config surfaces pin local Crossref/OpenAlex before the online API fallback tier.
6. Desktop and 390px contracts are executable tests, including a wrapping full-width mobile picker.
7. This slice does **not** authorize deletion of the Hub reference or claim full UI/search migration.
8. Operator screenshot acceptance: Library empty and filtered-empty states must be distinct and name visible actions; Citation Graph must start with DOI guidance, an empty required seed, and a visibly labelled/accessible maximum-paper control at desktop and 390px.

## Remaining migration work

- Port the Hub-quality source controls/readiness display and explicit per-source fallback behavior into the leaf UI.
- Build and benchmark the 10k–20k results path, including cancellation, virtualization/paging, filters, sorting, source counts, and preferences.
- Complete Library project semantics, batch enrichment progress/resume/provenance, and citation-graph parity.
- Add real standalone and host-mounted browser coverage at desktop and 390px, then compare against the Hub reference.
- Switch Hub to a thin mount only after these gates pass; delete neither reference nor host integration in this slice.
