# Citation Graph Module

Build and analyze citation networks for academic papers using CrossRef data.

## Features

- **Citation extraction**: Forward and reverse citation lookups
- **Similarity metrics**: Co-citation and bibliographic coupling analysis
- **Network building**: Construct graphs of related papers
- **Export formats**: JSON for D3.js, vis.js, Cytoscape

## Quick Start

```python
from scitex_scholar.citation_graph import CitationGraphBuilder

# Endpoint resolved from SCITEX_SCHOLAR_CROSSREF_API_URL, or pass
# api_url="http://localhost:31291" explicitly.
builder = CitationGraphBuilder()

# Build citation network for a paper
graph = builder.build("10.1038/s41586-020-2008-3", top_n=20)

# Export for visualization
builder.export_json(graph, "network.json")

# Get paper summary
summary = builder.get_paper_summary("10.1038/s41586-020-2008-3")
```

## Architecture

```
citation_graph/
├── __init__.py          # Package exports
├── builder.py           # CitationGraphBuilder (main interface)
├── database_http.py     # crossref-local HTTP metadata/graph client
├── models.py            # Data models (PaperNode, CitationEdge, CitationGraph)
├── _saved_graph_store.py # User graph recipes + optional derived store mirror
└── README.md            # This file
```

## Similarity Metrics

### 1. Co-citation
Papers are related if they are frequently cited together.
- **Algorithm**: Find papers that appear together in reference lists
- **Weight**: 2.0 (default)
- **Use case**: Find foundational/seminal works in the same field

### 2. Bibliographic Coupling
Papers are related if they cite similar references.
- **Algorithm**: Count shared references between papers
- **Weight**: 2.0 (default)
- **Use case**: Find papers addressing similar problems/methods

### 3. Direct Citations
Papers directly citing or cited by the seed paper.
- **Weight**: 1.0 (default)
- **Use case**: Find immediately related work

## Performance

Based on experiments with 47M+ citations:

| Operation | Time | Status |
|-----------|------|--------|
| Forward citations | 0.1ms | ⚡ Excellent |
| Reverse citations | 3.3s | ✓ Good |
| Co-citation | 3.2s | ✓ Good |
| Bibliographic coupling | 25s | ⚠️ Needs optimization |
| **Full network build** | **~30s** | ✓ Acceptable |

## Backend

Requires a running [crossref-local](https://github.com/scitex-ai/crossref-local)
server. Scholar reaches it over HTTP and never opens its data files: the
package that owns the corpus is the one that reads it.

Two behavioural notes that follow from the HTTP boundary:

- `get_citations` returns year `0` for every citing DOI — the API does not
  return years alongside citing DOIs.
- Co-citation and bibliographic coupling are computed client-side from
  citation lists, with a fan-out cap, rather than as one server-side join.

## Example Output

```json
{
  "seed": "10.1038/s41586-020-2008-3",
  "nodes": [
    {
      "id": "10.1038/s41586-020-2008-3",
      "title": "A Randomized Controlled Trial...",
      "year": 2020,
      "authors": ["Smith J", "Jones A"],
      "journal": "Nature",
      "similarity_score": 100.0
    },
    ...
  ],
  "edges": [
    {
      "source": "10.1038/s41586-020-2008-3",
      "target": "10.1016/j.cell.2019.11.025",
      "type": "cites"
    },
    ...
  ]
}
```

## Future Enhancements

- [ ] Redis caching for popular papers
- [ ] Async/parallel query execution
- [ ] Additional similarity metrics (topic modeling, author networks)
- [ ] GraphQL API
- [ ] Real-time updates

## References

- Co-citation: Small, H. (1973). Co-citation in the scientific literature. *J. Am. Soc. Inf. Sci.*
- Bibliographic coupling: Kessler, M. M. (1963). Bibliographic coupling. *American Documentation*
- Connected Papers (inspiration): https://www.connectedpapers.com/


## Graph Library

The Citation Graph tab builds networks from works selected in Search or Library.
Its Graph Library saves named recipes, including all seed DOIs (up to 20) and
the graph width. Load rebuilds the network from those seeds; Rename and Delete
operate on the saved recipe, without changing papers in the scholarly library.
Legacy single-`seed_doi` recipes remain loadable.

Recipes live in `SAVED_GRAPHS/saved_graphs.json` under the user's Scholar library.
Standalone defaults to `~/.scitex/scholar/library`. A mounted host may supply the
request-aware `SCITEX_USER_HOME_PROVIDER`; the leaf then uses that authorized
home's `.scitex/scholar/library`. Explicit trusted request roots and the existing
`SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE` administrator override take precedence.
The provider owns user authorization; the leaf imports no Hub models and does
not derive a home from a client-supplied project or path.

The user file is authoritative, including an empty library. Updates hold a
cross-process file lock and replace a same-directory temporary file atomically;
invalid existing JSON is reported rather than discarded. A missing file may
import legacy database-only recipes once. The shared store is a best-effort
mirror: stale or read-only database rows cannot hide recent file saves or bring
back deleted recipes. New optional mirror fields need the normal authorized
store-schema provisioning; requests keep their file persistence when that
mirror is unavailable. The mirror uses the public `scitex_dev.store.Store`
`rows`, `revision`, and `is_hidden` methods.
