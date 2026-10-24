"""scitex-scholar's OWN agent guardrails, declared as a leaf of the federation.

Registered under the ``scitex_dev.hooks`` entry-point group in pyproject.toml
exactly like scitex-storage's provider
(``scitex_storage._hook_rules:provide``). scitex-dev holds no privileged
position in the corpus it aggregates, and neither does this module: it
declares scholar's scope, nothing else.

SCOPE. These are the scholar-DATA guardrails -- search/save/enrich
provenance, no silent overwrites of library metadata, thin-view discipline
(the CUI owns the logic; ``_django`` only renders and forwards). Guardrails
about the dev workflow belong to scitex-dev; guardrails about moving and
deleting research data belong to scitex-storage. Each declares its own.

PROVENANCE. Every rule below was read off the implementation and the
incident record, not reconstructed from documentation:

1. Saved graphs/graph CRUD keep the file as the authoritative store with
   the shared store as a derived mirror (backfill, never migrate-and-drop).
   A store outage serves the file -- a write that succeeds locally while
   reaching nobody is the 2026-08-09 failure mode, reproduced by design
   if the file were dropped.
2. ``api/search`` fails CLOSED (400) on malformed range filters and drops
   unknown source names with a warning -- never fail the search for a bad
   source value (hub parity: ``normalize_sources``).
3. Bulk library verbs (save-bulk/enrich) are explicit actions over checked
   rows only; the request path never invents a paper the user did not check.
4. ``api/graphs/*`` and ``api/library/*`` are per-request-user scoped
   (``_library_root_for``); the shared service-account home is never
   exposed across authenticated users.

``implemented_in`` names the code that enforces the rule today. Where the
binding is in-process only, ``script`` is None and the rule is enforced by
the named implementation, not by a shell shim -- declared here so the scope
is enumerable and auditable, exactly as the federation intends.
"""

from __future__ import annotations

try:
    from scitex_dev.hooks import HookRule
except ImportError:  # pragma: no cover - provider loads under scitex-dev
    HookRule = None  # type: ignore[assignment]


def _rule(**kw):  # noqa: ANN001, ANN202 - mirrors scitex-dev's own helper shape
    kw.setdefault("event", "pre-tool-use")
    return HookRule(**kw)


def provide() -> list:
    """Return scitex-scholar's declared guardrails (leaf scope)."""
    if HookRule is None:  # pragma: no cover - provider loads under scitex-dev
        return []
    return [
        _rule(
            id="scholar.file-authoritative-store-derived",
            rule="Saved graphs keep the per-user file authoritative with the "
            "shared store as a derived mirror (backfill on read, best-effort "
            "on write); a store outage serves the file and never fails the "
            "request.",
            reason="Dropping the file for the store would reproduce the "
            "2026-08-09 failure mode by design: a write that succeeds "
            "locally while reaching nobody. The file is the migration "
            "source; the store has no delete verb (hide only).",
            severity="deny",
            matches=("Bash",),
            implemented_in="scitex_scholar._django.views "
            "(_load_saved_graphs/_write_saved_graphs) + "
            "scitex_scholar.citation_graph._saved_graph_store",
        ),
        _rule(
            id="scholar.search-fails-closed",
            rule="api/search fails closed (400) on malformed range filters "
            "and drops unknown source names with a warning; never fail the "
            "search for a bad source value.",
            reason="A source checkbox typo must not void a whole search. "
            "normalize_sources keeps the tiered default on empty/all-unknown "
            "selections (old-direct Sources parity).",
            severity="deny",
            matches=("Bash",),
            implemented_in="scitex_scholar._django.views (search, "
            "_parse_range_filters) + "
            "scitex_scholar.search_engines._source_tiers.normalize_sources",
        ),
        _rule(
            id="scholar.bulk-verbs-explicit-rows-only",
            rule="Bulk library verbs (save-bulk/enrich/download-pdfs) act "
            "only on explicitly checked rows; the request path never invents "
            "a paper the user did not check.",
            reason="Library provenance: every MASTER row must trace to a "
            "user-checked result or an explicit import, never to an ambient "
            "selection the UI guessed.",
            severity="deny",
            matches=("Bash",),
            implemented_in="scitex_scholar._django.views "
            "(library_save_bulk/library_enrich/library_download_pdfs) + "
            "scitex_scholar.storage._master_store",
        ),
        _rule(
            id="scholar.per-user-root-scope",
            rule="api/graphs/* and api/library/* resolve the user root per "
            "request (_library_root_for: bound root, then per-user mounted "
            "dir, then home library); the shared service-account home is "
            "never exposed across authenticated users.",
            reason="The hub runs one server process for all users. A "
            "process-global library root would leak one user's papers to "
            "everyone.",
            severity="deny",
            matches=("Bash",),
            implemented_in="scitex_scholar._django.views "
            "(_library_root_for/_mounted_user_root/_safe_username)",
        ),
        _rule(
            id="scholar.thin-view-cui-owns-logic",
            rule="The _django layer only validates, adapts HTTP, and "
            "renders; search/enrich/download/graph logic lives in the CUI "
            "package (search_engines/storage/citation_graph/cli). A view "
            "that computes domain answers is a layering fault.",
            reason="Operator directive 2026-10-24: the backend is "
            "scitex-scholar's CUI and _django is only an interface for "
            "users. Logic in the view cannot be reached by the CLI, MCP, "
            "or skills -- the API-consistency rule.",
            severity="warn",
            matches=("Bash",),
            implemented_in="scitex_scholar._django.views (thin adapters) + "
            "scitex_scholar.citation_graph._saved_graph_store (new CUI "
            "home for saved-graph persistence)",
        ),
    ]


# EOF
