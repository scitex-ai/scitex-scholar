# Scholar Details controls

Scholar uses the SDK main/details panes for width, resizing, collapse and phone
navigation. Search controls are leaf-owned inside that shared pane, in the
reference UI order: Sources, Sorters, Filters. Groups use native `details` and
`summary` elements for pointer and keyboard access.

Sources contains the search mode, source checkboxes, cache option and configured
Crossref status. Configured does not mean a successful connectivity probe.
Query syntax remains available through the query field's help button.

Sorters reorder only results already loaded by the current search. Year,
citations and impact factor cycle descending, ascending, then relevance; Title
selects alphabetical order. Relevance restores the provider's arrival order.
Unknown numeric values remain last in either direction, real zeroes remain
numeric, and ties preserve arrival order. Sorting never fetches another page or
clears work selection. It is not a sort over an entire remote corpus.

Filters pairs the lower and upper bounds for year, citations and impact factor.
Ranges apply to the next submitted search. The loaded-source selector filters
already loaded rows. Reset filters clears those bounds and the loaded-source
filter without starting a search, changing selected databases or clearing work
selection. Existing server validation remains authoritative for submitted ranges.

Source evidence: `workspace_content.html`, `search.js`, `search-order.js` and
`search-details.css` under `src/scitex_scholar/_django/`. New assets use the SDK
`app_static` helper; no manual cache-version string is needed.
