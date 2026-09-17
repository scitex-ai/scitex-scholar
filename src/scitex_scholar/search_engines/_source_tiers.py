#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-tier policy: NAS-local corpora first, public APIs only as fallback.

``config/_categories/search_engines.yaml`` (and ``config/default.yaml``) declare::

    source_tiers:
      primary:         [CrossRefLocal, OpenAlexLocal]
      online_fallback: [CrossRef, OpenAlex]

Until this module existed that declaration was DECLARATIVE ONLY: the config
named the local corpora as primary, and both search pipelines still built a
hardcoded dict of the five ONLINE engines, so the GUI queried the network first
and the NAS corpora never at all. This module turns the declaration into
execution:

* :class:`LocalCorpusSearchEngine` adapts the local CrossRef/OpenAlex corpora
  (``local_dbs.unified``) to the same ``search_by_keywords`` interface the
  online engines implement, so a tier is just a dict of engines.
* :func:`declared_source_tiers` reads the policy from config (env-overridable
  through the normal ScholarConfig cascade).
* :func:`build_tiered_engines` resolves each configured NAME to an instance.
* :func:`resolve_tier` decides which tier served a query and why, so the
  fallback is explicit and reportable instead of silent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import scitex_logging as logging

from scitex_scholar.search_engines._BaseSearchEngine import BaseSearchEngine
from scitex_scholar.search_engines.individual.ArXivSearchEngine import ArXivSearchEngine
from scitex_scholar.search_engines.individual.CrossRefSearchEngine import (
    CrossRefSearchEngine,
)
from scitex_scholar.search_engines.individual.OpenAlexSearchEngine import (
    OpenAlexSearchEngine,
)
from scitex_scholar.search_engines.individual.PubMedSearchEngine import (
    PubMedSearchEngine,
)
from scitex_scholar.search_engines.individual.SemanticScholarSearchEngine import (
    SemanticScholarSearchEngine,
)

logger = logging.getLogger(__name__)

#: Configured name -> the local corpora it queries (``local_dbs.unified``
#: source names). These are the NAS adapters, not network clients.
LOCAL_CORPUS_SOURCES: Dict[str, Tuple[str, ...]] = {
    "CrossRefLocal": ("crossref",),
    "OpenAlexLocal": ("openalex",),
}

#: Configured name -> the online engine class. Only reached as a fallback.
ONLINE_ENGINES: Dict[str, type] = {
    "PubMed": PubMedSearchEngine,
    "CrossRef": CrossRefSearchEngine,
    "arXiv": ArXivSearchEngine,
    "Semantic_Scholar": SemanticScholarSearchEngine,
    "OpenAlex": OpenAlexSearchEngine,
}

#: Used when config carries no ``source_tiers`` block at all. Keeps a
#: mis-specified config from silently reverting to online-first behaviour.
DEFAULT_SOURCE_TIERS: Dict[str, List[str]] = {
    "primary": ["CrossRefLocal", "OpenAlexLocal"],
    "online_fallback": ["CrossRef", "OpenAlex"],
}


def available_local_corpora() -> set:
    """Which local corpora this install can actually query.

    The corpora ship as optional packages (``crossref_local`` /
    ``openalex_local``); a deployment without them must SAY it fell back to the
    network, not pretend the primary tier ran.
    """
    from scitex_dev import try_import_optional

    available = set()
    if try_import_optional("crossref_local") is not None:
        available.add("crossref")
    if try_import_optional("openalex_local") is not None:
        available.add("openalex")
    return available


class CorpusUnavailable(RuntimeError):
    """A configured local corpus cannot be queried in this installation."""


def default_corpus_search(query: str, limit: int, sources: list):
    """Query the installed local corpora through ``local_dbs.unified``.

    The ``local_dbs`` PACKAGE re-exports its crossref/openalex shims, and those
    raise ImportError when the optional corpora are absent -- translated here
    into :class:`CorpusUnavailable` so "this deployment has no NAS corpora" is
    a reportable state rather than an exception that kills the user's search.
    """
    try:
        from scitex_scholar.local_dbs import unified
    except ImportError as exc:
        raise CorpusUnavailable(str(exc)) from exc
    return unified.search(query, limit=limit, sources=sources)


class LocalCorpusSearchEngine(BaseSearchEngine):
    """Search the NAS-local corpora through the online engines' interface.

    Wraps ``local_dbs.unified`` so the pipelines treat a local corpus exactly
    like any other engine: same ``search_by_keywords(query, filters,
    max_results)`` call, same standardized result dicts, same Paper conversion
    downstream. No network client is constructed here at all.

    ``available`` and ``search`` are injection seams (the collaborators, as
    parameters): production passes neither, and they exist so a test can drive
    the corpus-absent path and inspect the work mapping without patching
    anything.
    """

    def __init__(
        self,
        engine_name: str,
        sources: Tuple[str, ...],
        available=None,
        search=None,
    ):
        self._engine_name = engine_name
        self._sources = tuple(sources)
        self._available = available or available_local_corpora
        self._search = search or default_corpus_search

    @property
    def name(self) -> str:
        """Engine name for logging (the configured tier name)."""
        return self._engine_name

    @property
    def sources(self) -> Tuple[str, ...]:
        """Local corpora this engine queries, e.g. ``("crossref",)``."""
        return self._sources

    def search_by_keywords(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query the local corpora; ``[]`` when this install cannot.

        Year/citation thresholds are NOT pushed here: the pipelines apply them
        after aggregation (``_apply_threshold_filters``), which keeps the local
        and online tiers filtered by identical rules.
        """
        usable = self._available().intersection(self._sources)
        if not usable:
            logger.warning(
                f"{self._engine_name}: local corpus unavailable "
                f"(sources={list(self._sources)} not installed)"
            )
            return []

        try:
            result = self._search(query, limit=max_results, sources=sorted(usable))
        except CorpusUnavailable as exc:
            logger.warning(
                f"{self._engine_name}: local corpus package not importable ({exc})"
            )
            return []
        except Exception as exc:  # a broken corpus must not kill the search
            logger.error(f"{self._engine_name}: local corpus search failed: {exc}")
            return []

        return [self._to_result_dict(work) for work in result.works]

    def _to_result_dict(self, work) -> Dict[str, Any]:
        """One ``local_dbs`` UnifiedWork in the engines' standardized shape."""
        doi = work.doi or None
        return {
            "id": {"doi": doi, "doi_engines": [self._engine_name]},
            "basic": {
                "title": work.title,
                "authors": list(work.authors or []),
                "abstract": work.abstract,
            },
            "publication": {"year": work.year, "journal": work.journal},
            "metrics": {
                "citation_count": work.citation_count,
                "is_open_access": work.is_open_access,
            },
            "urls": {
                "doi_url": f"https://doi.org/{doi}" if doi else None,
                "pdf": work.oa_url,
            },
        }


def declared_source_tiers() -> Dict[str, List[str]]:
    """The configured tier policy (``source_tiers``), or the shipped default.

    Read through ScholarConfig, so the usual cascade applies: a deployment can
    point the corpora or the fallback list elsewhere by env/config without any
    code change.
    """
    try:
        from scitex_scholar.config import ScholarConfig

        declared = ScholarConfig().get("source_tiers")
    except Exception as exc:  # config is optional at this level
        logger.warning(f"source_tiers: falling back to defaults ({exc})")
        declared = None
    if not declared:
        return {tier: list(names) for tier, names in DEFAULT_SOURCE_TIERS.items()}
    return {tier: list(names) for tier, names in declared.items()}


def declared_engines() -> List[str]:
    """The configured ``engines:`` list -- every engine the leaf may call."""
    try:
        from scitex_scholar.config import ScholarConfig

        declared = ScholarConfig().get("engines")
    except Exception as exc:
        logger.warning(f"engines: falling back to the tier lists ({exc})")
        declared = None
    if not declared:
        return list(LOCAL_CORPUS_SOURCES) + list(ONLINE_ENGINES)
    return list(declared)


def build_tiered_engines(
    tiers: Optional[Dict[str, List[str]]] = None,
    email: Optional[str] = None,
    available=None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Resolve tier names to engine instances.

    Returns ``(primary, fallback)``. The fallback tier carries every declared
    online engine: the ones named in ``source_tiers.online_fallback`` first,
    then the rest of the configured ``engines`` list. That ORDER is the policy
    (the same-corpus public API is tried before the other databases); coverage
    is not narrowed by it, because dropping PubMed/arXiv/Semantic Scholar from a
    search would silently change results for reasons no user could see.

    A configured name that resolves to nothing is dropped WITH a warning rather
    than silently retried online -- an unresolvable primary name must be
    visible, because it changes which corpus answers the user's query.
    """
    tiers = tiers or declared_source_tiers()
    primary: Dict[str, Any] = {}
    fallback: Dict[str, Any] = {}

    for name in tiers.get("primary", []):
        sources = LOCAL_CORPUS_SOURCES.get(name)
        if sources is None:
            logger.warning(
                f"source_tiers: primary entry {name!r} has no local adapter; "
                f"skipped (known: {sorted(LOCAL_CORPUS_SOURCES)})"
            )
            continue
        primary[name] = LocalCorpusSearchEngine(name, sources, available=available)

    ordered_fallbacks = list(tiers.get("online_fallback", []))
    ordered_fallbacks += [
        name
        for name in declared_engines()
        if name in ONLINE_ENGINES
        and name not in ordered_fallbacks
        and name not in primary
    ]

    for name in ordered_fallbacks:
        engine_cls = ONLINE_ENGINES.get(name)
        if engine_cls is None:
            logger.warning(
                f"source_tiers: online_fallback entry {name!r} has no engine; "
                f"skipped (known: {sorted(ONLINE_ENGINES)})"
            )
            continue
        fallback[name] = engine_cls(email=email)

    return primary, fallback


def resolve_tier(
    primary_results: int,
    primary_engines: Dict[str, Any],
    min_primary_results: int = 1,
    available=None,
) -> Tuple[str, str]:
    """Which tier should serve the query, and the reason, from primary results.

    ``("primary", "")`` when the local corpora answered. Otherwise
    ``("online_fallback", <reason>)`` -- the reason distinguishes "the corpora
    answered with nothing" from "the corpora are not installed here", which
    have different fixes and must not read the same in a bug report.

    ``available`` is the corpus-availability collaborator as a parameter
    (defaults to the real probe), so a test can drive both reasons directly.
    """
    if primary_results >= min_primary_results:
        return "primary", ""
    if not primary_engines:
        return "online_fallback", "no primary (local corpus) engine configured"
    availability = available or available_local_corpora
    missing = sorted(
        {
            source
            for engine in primary_engines.values()
            for source in getattr(engine, "sources", ())
        }
        - availability()
    )
    if missing:
        return (
            "online_fallback",
            f"local corpora unavailable: {', '.join(missing)}",
        )
    return "online_fallback", "local corpora returned no results"


# EOF
