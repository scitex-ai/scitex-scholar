# Saved citation graph recipes

Select works in Search or Library and use **Graph** / **Graph selected** to
build a citation network. Selection alone does not save a paper or a graph.
The client accepts 1–20 distinct DOI seeds and refuses larger selections
explicitly. Graph Library provides **Save**, **Load**, **Rename**, and a
confirmation step for **Delete**.

A saved graph is a rebuild recipe: its name, seed DOI list, and per-seed
`top_n` setting. **Load** queries the configured citation backend again.
Nodes, edges, and positions are not frozen snapshots and can change when the
corpus changes. Legacy single-seed recipes remain loadable. These controls do
not claim an exhaustive citation closure or an all-results export.

The app declares both user and project support through the public SDK 0.3.17
`ScitexAppConfig.scope_capabilities` contract. GUI and development extras require
that minimum version; earlier SDKs do not expose this capability declaration.

The leaf resolves mounted user storage through the host's configured
`SCITEX_USER_HOME_PROVIDER`, yielding
`<user-home>/.scitex/scholar/library/SAVED_GRAPHS/saved_graphs.json`.
An explicit trusted `request.scholar_library_root` or administrator-configured
`SCITEX_SCHOLAR_MOUNTED_LIBRARY_BASE` takes precedence. A configured provider
that fails cannot silently fall back to the service account's home. Standalone
use retains the local library and its explicit root override.

`citation_graph/_saved_graph_store.py` owns persistence. A process lock and a
same-directory temporary file with atomic replacement protect file updates.
An existing JSON file, including an empty one, is authoritative. Only when it
is absent may listing migrate legacy database-only recipes. The shared store
is a best-effort mirror; stale mirror rows cannot resurrect deleted recipes.
Consequently, listing may perform migration or mirror maintenance and is not
a strictly side-effect-free filesystem operation.

`_django/views.py` adapts these operations at `api/graphs/{save,list,rename,delete}`
and resolves the authenticated mounted user's root. It does not import Hub
project models. Regression coverage includes owned temporary libraries,
concurrent updates, failed-write preservation, and multi-seed rebuild recipes.
