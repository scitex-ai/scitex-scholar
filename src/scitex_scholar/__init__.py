#!/usr/bin/env python3
"""SciTeX Scholar -- scientific paper search, enrichment, and management.

Quick Start:
    from scitex_scholar import Scholar, Paper, Papers

    scholar = Scholar()
    papers = scholar.search("deep learning")
    papers.save("results.bib")

Installation:
    pip install scitex-scholar

This module uses PEP 562 lazy `__getattr__` so `import scitex_scholar`
stays under 500ms cold-start. Submodules are imported on first attribute
access only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        __version__ = _v("scitex-scholar")
    except PackageNotFoundError:
        __version__ = "0.0.0+local"
    del _v, PackageNotFoundError
except ImportError:  # pragma: no cover — only on ancient Pythons
    __version__ = "0.0.0+local"
__author__ = "Yusuke Watanabe"


# Public API: declared for tab-completion and `list-python-apis`.
__all__ = [
    "__version__",
    "Scholar",
    "Paper",
    "Papers",
    "ScholarConfig",
    "ScholarAuthManager",
    "ScholarBrowserManager",
    "ScholarURLFinder",
    "CitationGraphBuilder",
    "plot_citation_graph",
    "to_bibtex",
    "to_ris",
    "to_endnote",
    "to_text_citation",
    "papers_to_format",
    "generate_cite_key",
    "make_citation_key",
    "from_connected_papers",
    "to_connected_papers",
    "apply_filters",
    "clean_abstract",
    "ensure_workspace",
    "SCHOLAR_AVAILABLE",
]


# Always-True flag: downstream shims (e.g. `scitex.scholar` re-export) check
# this without forcing every submodule to import. Lazy attribute access
# below validates each name on demand.
SCHOLAR_AVAILABLE = True


# Map of public name -> (submodule, attribute). Module is imported only
# when the attribute is requested.
_LAZY: dict[str, tuple[str, str]] = {
    "Scholar": (".core.Scholar", "Scholar"),
    "Paper": (".core.Paper", "Paper"),
    "Papers": (".core.Papers", "Papers"),
    "ScholarConfig": (".config", "ScholarConfig"),
    "ScholarAuthManager": (".auth", "ScholarAuthManager"),
    "ScholarBrowserManager": (".browser", "ScholarBrowserManager"),
    "ScholarURLFinder": (".url_finder", "ScholarURLFinder"),
    "CitationGraphBuilder": (".citation_graph", "CitationGraphBuilder"),
    "plot_citation_graph": (".citation_graph", "plot_citation_graph"),
    "to_bibtex": (".formatting", "to_bibtex"),
    "to_ris": (".formatting", "to_ris"),
    "to_endnote": (".formatting", "to_endnote"),
    "to_text_citation": (".formatting", "to_text_citation"),
    "papers_to_format": (".formatting", "papers_to_format"),
    "generate_cite_key": (".formatting", "generate_cite_key"),
    "make_citation_key": (".formatting", "make_citation_key"),
    "from_connected_papers": (".migration", "from_connected_papers"),
    "to_connected_papers": (".migration", "to_connected_papers"),
    "apply_filters": (".filters", "apply_filters"),
    "ensure_workspace": (".ensure_workspace", "ensure_workspace"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from importlib import import_module

        mod_name, attr = _LAZY[name]
        mod = import_module(mod_name, __name__)
        value = getattr(mod, attr)
        globals()[name] = value
        return value

    if name == "clean_abstract":
        from ._utils.text._TextNormalizer import TextNormalizer as _TN

        def clean_abstract(text: str) -> str:
            """Strip HTML/JATS XML tags from a CrossRef-style abstract."""
            return _TN.strip_html_tags(text)

        globals()["clean_abstract"] = clean_abstract
        return clean_abstract

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + __all__))


if TYPE_CHECKING:
    # Re-export types for static checkers without paying import cost at runtime.
    from .auth import ScholarAuthManager  # noqa: F401
    from .browser import ScholarBrowserManager  # noqa: F401
    from .citation_graph import (  # noqa: F401
        CitationGraphBuilder,
        plot_citation_graph,
    )
    from .config import ScholarConfig  # noqa: F401
    from .core.Paper import Paper  # noqa: F401
    from .ensure_workspace import ensure_workspace  # noqa: F401
    from .core.Papers import Papers  # noqa: F401
    from .core.Scholar import Scholar  # noqa: F401
    from .filters import apply_filters  # noqa: F401
    from .formatting import (  # noqa: F401
        generate_cite_key,
        make_citation_key,
        papers_to_format,
        to_bibtex,
        to_endnote,
        to_ris,
        to_text_citation,
    )
    from .migration import from_connected_papers, to_connected_papers  # noqa: F401
    from .url_finder import ScholarURLFinder  # noqa: F401


# EOF
