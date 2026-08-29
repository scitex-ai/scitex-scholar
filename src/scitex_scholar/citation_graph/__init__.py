"""
Citation Graph Module

Build and analyze citation networks for academic papers using CrossRef data.

This module provides tools to:
- Extract citation relationships
- Calculate paper similarity (co-citation, bibliographic coupling)
- Build citation network graphs
- Export for visualization (D3.js, vis.js, Cytoscape)

Citation data is served by crossref-local over HTTP.

Example (auto-detected endpoint):
    >>> from scitex_scholar.citation_graph import CitationGraphBuilder
    >>> builder = CitationGraphBuilder()
    >>> graph = builder.build("10.1038/s41586-020-2008-3", top_n=20)

Example (explicit endpoint):
    >>> builder = CitationGraphBuilder(api_url="http://localhost:31291")
    >>> graph = builder.build("10.1038/s41586-020-2008-3", top_n=20)
"""

from .builder import CitationGraphBuilder
from .models import CitationEdge, CitationGraph, PaperNode
from .visualization import list_backends, plot_citation_graph

__all__ = [
    "CitationGraphBuilder",
    "PaperNode",
    "CitationEdge",
    "CitationGraph",
    "plot_citation_graph",
    "list_backends",
]
