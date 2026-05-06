#!/usr/bin/env python3
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/__main__.py

"""Scholar CLI entry point - Subcommand-based interface.

Clean interface routing to battle-tested pipeline implementations:
- single: Process single paper (DOI or title)
- parallel: Process multiple papers in parallel
- bibtex: Process papers from BibTeX file
- mcp: Start MCP server for LLM integration
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import scitex_logging as logging

logger = logging.getLogger(__name__)


def create_parser():
    """Create main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="scitex-scholar",
        description="""
SciTeX Scholar - Scientific Literature Management
═════════════════════════════════════════════════

Clean subcommand interface to battle-tested pipelines:
  single   - Process a single paper (DOI or title)
  parallel - Process multiple papers in parallel
  bibtex   - Process papers from BibTeX file
  mcp      - Start MCP server for LLM integration

STORAGE: ~/.scitex/scholar/library/
  MASTER/{8DIGITID}/  - Centralized storage (no duplicates)
  {project}/          - Project symlinks to MASTER
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=False,
    )

    # ========================================
    # Subcommand: single
    # ========================================
    single_parser = subparsers.add_parser(
        "single",
        help="Process a single paper",
        description="Process a single paper from DOI or title through full pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    single_parser.add_argument(
        "--doi",
        type=str,
        help='DOI of the paper (e.g., "10.1038/nature12373")',
        metavar="DOI",
    )
    single_parser.add_argument(
        "--title",
        type=str,
        help="Paper title (will resolve DOI automatically)",
        metavar="TITLE",
    )
    single_parser.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    single_parser.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for PDF download (default: stealth)",
    )
    single_parser.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Chrome profile name (default: system)",
    )
    single_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-download even if files exist",
    )

    # ========================================
    # Subcommand: parallel
    # ========================================
    parallel_parser = subparsers.add_parser(
        "parallel",
        help="Process multiple papers in parallel",
        description="Process multiple papers using parallel workers with dedicated browser profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parallel_parser.add_argument(
        "--dois",
        type=str,
        nargs="+",
        help="Space-separated DOIs",
        metavar="DOI",
    )
    parallel_parser.add_argument(
        "--titles",
        type=str,
        nargs="+",
        help="Space-separated paper titles (use quotes for multi-word titles)",
        metavar="TITLE",
    )
    parallel_parser.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    parallel_parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
        metavar="N",
    )
    parallel_parser.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for all workers (default: stealth)",
    )
    parallel_parser.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Base Chrome profile to sync from (default: system)",
    )

    # ========================================
    # Subcommand: bibtex
    # ========================================
    bibtex_parser = subparsers.add_parser(
        "bibtex",
        help="Process papers from BibTeX file",
        description="Process all papers from a BibTeX file in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bibtex_parser.add_argument(
        "--bibtex",
        type=str,
        required=True,
        help="Path to BibTeX file",
        metavar="FILE",
    )
    bibtex_parser.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    bibtex_parser.add_argument(
        "--output",
        type=str,
        help="Output path for enriched BibTeX (default: {input}_processed.bib)",
        metavar="FILE",
    )
    bibtex_parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
        metavar="N",
    )
    bibtex_parser.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for all workers (default: stealth)",
    )
    bibtex_parser.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Base Chrome profile to sync from (default: system)",
    )

    # ========================================
    # Subcommand: mcp
    # ========================================
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP (Model Context Protocol) server commands",
        description="MCP (Model Context Protocol) server commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command", required=False)

    mcp_start = mcp_sub.add_parser(
        "start",
        help="Start the scitex-scholar MCP server",
        description="Start the standalone scitex-scholar MCP server.",
    )
    mcp_start.add_argument(
        "--dry-run", action="store_true", help="Print launch plan without starting."
    )

    mcp_sub.add_parser(
        "list-tools",
        help="List available MCP tools",
        description=(
            "Print the MCP tool names exposed by scitex-scholar (scholar_*). "
            "Read-only; does not start the server."
        ),
    )

    mcp_sub.add_parser(
        "doctor",
        help="Check MCP server dependencies",
        description="Verify fastmcp is installed and the server module imports.",
    )

    mcp_install = mcp_sub.add_parser(
        "install",
        help="Show MCP installation instructions",
        description="Print installation / Claude Code config instructions.",
    )
    mcp_install.add_argument(
        "--claude-code",
        action="store_true",
        help="Show Claude Code MCP config snippet.",
    )

    # ========================================
    # Subcommand: highlight
    # ========================================
    # ========================================
    # Subcommand: link-project-tree
    # ========================================
    from .cli._project_tree import register_subparser as _register_link_project_tree
    from .pdf_highlight._cli import build_parser as _build_highlight_parser

    _register_link_project_tree(subparsers)

    # ========================================
    # Subcommands: materialize / dematerialize
    # ========================================
    from .cli._materialize import register_subparsers as _register_materialize

    _register_materialize(subparsers)

    # ========================================
    # Subcommand: db  (library index)
    # ========================================
    from .cli._library_index import register_subparser as _register_db

    _register_db(subparsers)

    highlight_parser = subparsers.add_parser(
        "highlight",
        help="Overlay semantic highlights on a PDF",
        description=(
            "Tag each paragraph of a PDF with a rhetorical role "
            "(claim/method/limitation/supportive/contradictive) via Claude, "
            "then write a copy with colour-coded highlight annotations."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _build_highlight_parser(highlight_parser)

    return parser


async def run_single_pipeline(args):
    """Run single paper pipeline."""
    from .pipelines.ScholarPipelineSingle import ScholarPipelineSingle

    # Validate input
    if not args.doi and not args.title:
        logger.error("Either --doi or --title is required")
        return 1

    doi_or_title = args.doi if args.doi else args.title

    logger.info(f"Running single paper pipeline: {doi_or_title}")

    pipeline = ScholarPipelineSingle(
        browser_mode=args.browser_mode,
        chrome_profile=args.chrome_profile,
    )

    paper, symlink_path = await pipeline.process_single_paper(
        doi_or_title=doi_or_title,
        project=args.project,
        force=args.force,
    )

    logger.success("Single paper pipeline completed")
    return 0


async def run_parallel_pipeline(args):
    """Run parallel papers pipeline."""
    from .pipelines.ScholarPipelineParallel import ScholarPipelineParallel

    # Validate input
    if not args.dois and not args.titles:
        logger.error("Either --dois or --titles is required")
        return 1

    # Combine DOIs and titles into single list
    queries = []
    if args.dois:
        queries.extend(args.dois)
    if args.titles:
        queries.extend(args.titles)

    logger.info(
        f"Running parallel pipeline: {len(queries)} papers with {args.num_workers} workers"
    )

    pipeline = ScholarPipelineParallel(
        num_workers=args.num_workers,
        browser_mode=args.browser_mode,
        base_chrome_profile=args.chrome_profile,
    )

    papers = await pipeline.process_papers_from_list_async(
        doi_or_title_list=queries,
        project=args.project,
    )

    logger.success(f"Parallel pipeline completed: {len(papers)} papers processed")
    return 0


async def run_bibtex_pipeline(args):
    """Run BibTeX file pipeline."""
    from pathlib import Path

    from .pipelines.ScholarPipelineBibTeX import ScholarPipelineBibTeX

    bibtex_path = Path(args.bibtex)
    if not bibtex_path.exists():
        logger.error(f"BibTeX file not found: {bibtex_path}")
        return 1

    logger.info(f"Running BibTeX pipeline: {bibtex_path}")

    pipeline = ScholarPipelineBibTeX(
        num_workers=args.num_workers,
        browser_mode=args.browser_mode,
        base_chrome_profile=args.chrome_profile,
    )

    papers = await pipeline.process_bibtex_file_async(
        bibtex_path=bibtex_path,
        project=args.project,
        output_bibtex_path=args.output,
    )

    logger.success(f"BibTeX pipeline completed: {len(papers)} papers processed")
    return 0


async def run_mcp_server():
    """Run MCP server."""
    from .mcp_server import main as mcp_main

    logger.info("Starting Scholar MCP server...")
    import inspect
    from typing import Any, cast

    result: Any = mcp_main()
    if inspect.isawaitable(result):
        await cast(Any, result)
    return 0


async def main_async():
    """Main async entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # No subcommand: print help to stdout and exit 0
    if args.command is None:
        parser.print_help()
        return 0

    # Route to appropriate pipeline
    if args.command == "single":
        return await run_single_pipeline(args)
    elif args.command == "parallel":
        return await run_parallel_pipeline(args)
    elif args.command == "bibtex":
        return await run_bibtex_pipeline(args)
    elif args.command == "mcp":
        from .cli._mcp_commands import run_mcp_subcommand

        return await run_mcp_subcommand(args, run_server=run_mcp_server)
    elif args.command == "highlight":
        from .pdf_highlight._cli import run as run_highlight

        return run_highlight(args)
    elif args.command == "link-project-tree":
        from .cli._project_tree import run as run_link_project_tree

        return run_link_project_tree(args)
    elif args.command == "materialize":
        from .cli._materialize import run_materialize

        return run_materialize(args)
    elif args.command == "dematerialize":
        from .cli._materialize import run_dematerialize

        return run_dematerialize(args)
    elif args.command == "db":
        from .cli._library_index import run as run_db

        return run_db(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


def main():
    """Synchronous entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())


# EOF
