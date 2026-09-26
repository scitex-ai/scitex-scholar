#!/usr/bin/env python3
"""
Example usage of the citation_graph module.

Run this from the scitex-code root:
    python -m scitex_scholar.citation_graph.example
"""

import sys
from pathlib import Path

import scitex_logging as slogging

logger = slogging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scitex_scholar.citation_graph import CitationGraphBuilder


def main():
    logger.info("=" * 70)
    logger.info("  Citation Graph Example")
    logger.info("=" * 70)

    # Endpoint comes from SCITEX_SCHOLAR_CROSSREF_API_URL when set,
    # otherwise crossref-local's own default. Requires a running
    # crossref-local server.
    builder = CitationGraphBuilder()
    logger.info(f"\nCrossRef API: {builder.api_url}")

    # Example DOI (a well-cited paper)
    seed_doi = "10.1001/2013.jamapsychiatry.4"

    # Get paper summary
    logger.info(f"\n1. Getting paper summary for {seed_doi}...")
    summary = builder.get_paper_summary(seed_doi)

    if summary:
        logger.info(f"\nPaper: {summary['title']}")
        logger.info(f"Authors: {', '.join(summary['authors'][:3])}")
        logger.info(f"Year: {summary['year']}")
        logger.info(f"Journal: {summary['journal']}")
        logger.info(f"References: {summary['reference_count']}")
        logger.info(f"Citations: {summary['citation_count']}")
    else:
        logger.error("Paper not found in database")
        return 1

    # Build citation network
    logger.info("\n2. Building citation network (top 20 papers)...")
    graph = builder.build(seed_doi, top_n=20)

    logger.info("\nNetwork built:")
    logger.info(f"  Nodes: {graph.node_count}")
    logger.info(f"  Edges: {graph.edge_count}")

    # Show top papers by similarity
    logger.info("\nTop 10 most similar papers:")
    logger.info(f"{'Rank':<5} {'Score':<7} {'Year':<6} {'Title':<60}")
    logger.info("-" * 85)

    sorted_nodes = sorted(graph.nodes, key=lambda n: n.similarity_score, reverse=True)

    for i, node in enumerate(sorted_nodes[:11], 1):
        if node.doi.lower() == seed_doi.lower():
            continue
        logger.info(
            f"{i:<5} {node.similarity_score:<7.1f} {node.year:<6} {node.title[:60]:<60}"
        )

    # Export to JSON
    output_path = Path(__file__).parent / "example_output.json"
    builder.export_json(graph, str(output_path))
    logger.info(f"\n3. Network exported to: {output_path}")
    logger.info(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")

    logger.success("\n✅ Example complete!")
    logger.info("\nNext steps:")
    logger.info("  - Open example_output.json to see the graph data")
    logger.info("  - Use this JSON with D3.js, vis.js, or Cytoscape for visualization")
    logger.info("  - Integrate with scitex-cloud for API endpoints")

    return 0


if __name__ == "__main__":
    sys.exit(main())
