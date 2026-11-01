# Local Crossref result pages

Selecting only **Crossref (SciTeX)** in the Search tab uses the package-owned
`GET api/search/page` route. `ScholarSearchEngine.search_page()` delegates to
`search_engines/_crossref_pages.py` and the configured `crossref_local.search()`.
The established multi-source `search()` and `api/search` list APIs stay intact.

Parameters are `q`, `sources=crossref_local`, `offset` (non-negative, default 0),
and `page_size` (1–1000, default 50). There is no 1000-total-result ceiling on
this page route. Each request remains bounded; the browser fetches another page
only when **Load more** is pressed. Online and multiple-source selections use
the existing bounded search and show that no global total is available.

`metadata.pagination` reports `offset`, `page_size`, `source_returned`,
`returned`, `total`, `total_scope`, `has_more`, and `next_offset`.

- `total` is the provider's source match count **before** Scholar threshold/text
  filters and deduplication. It is not a count of filtered papers or a combined
  count across databases.
- The next offset advances by source records scanned, even if the entire page
  is removed by filters. This prevents a filtered-empty page from ending the
  search prematurely.
- Keyword, year, citation/impact-factor thresholds and title/author/journal
  include/exclude query filters apply to scanned pages. Open-access and document
  type filters are refused explicitly because this provider cannot reliably
  supply those attributes; use a suitable additional source in bounded mode.
- Sorting and source filtering in the browser operate on loaded papers.
  Previously selected papers remain selected when more records arrive.
- Source ingestion may change totals/order between requests. Loaded rows are
  deduplicated by DOI/title; this is not a snapshot or an all-results export.
  Repeated loading can still grow browser memory; no virtualization claim is made.

Regression evidence lives in `tests/scitex_scholar/_django/test_search_pages.py`:
an owned SQLite FTS corpus with 1055 records exercises offset 1000, continuation,
exhaustion, filtered-empty pages, query filters, and API validation. An actual
configured-provider check on compute-03 also returned records at offset 1000.
