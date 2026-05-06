#!/usr/bin/env python3
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/__main__.py

"""Scholar CLI entry point — noun-verb subcommand interface.

Top-level groups:

- ``paper``   — operations on a single paper or a small set of papers
    - ``paper process``  → was ``single``   (process one paper)
    - ``paper batch``    → was ``parallel`` (process many papers in parallel)
- ``bibtex`` — operations on a BibTeX file
    - ``bibtex process`` → was ``bibtex``   (process every entry)
- ``mcp``    — MCP server commands {start, list-tools, doctor, install}
- ``pdf``    — PDF post-processing
    - ``pdf highlight`` → was ``highlight``
- ``library``— library-tree management
    - ``library link-project-tree`` → was ``link-project-tree``
    - ``library materialize``       → was ``materialize``
    - ``library dematerialize``     → was ``dematerialize``
    - ``library db {build,migrate,lookup,list,dedupe,audit}`` → was ``db``

The pre-1.3.0 top-level forms (``single``, ``parallel``, ``bibtex``, ``highlight``,
``link-project-tree``, ``materialize``, ``dematerialize``, ``db``) remain as
**deprecation aliases** — they parse cleanly, emit a one-line ``DeprecationWarning``
to stderr, and dispatch to the same handler as the new noun-verb form. The
aliases will be removed in 1.4.0.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import scitex_logging as logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument builders (shared between new noun-verb forms and deprecated aliases)
# ---------------------------------------------------------------------------


def _add_paper_process_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--doi",
        type=str,
        help='DOI of the paper (e.g., "10.1038/nature12373")',
        metavar="DOI",
    )
    p.add_argument(
        "--title",
        type=str,
        help="Paper title (will resolve DOI automatically)",
        metavar="TITLE",
    )
    p.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    p.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for PDF download (default: stealth)",
    )
    p.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Chrome profile name (default: system)",
    )
    p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-download even if files exist",
    )


def _add_paper_batch_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--dois",
        type=str,
        nargs="+",
        help="Space-separated DOIs",
        metavar="DOI",
    )
    p.add_argument(
        "--titles",
        type=str,
        nargs="+",
        help="Space-separated paper titles (use quotes for multi-word titles)",
        metavar="TITLE",
    )
    p.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    p.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
        metavar="N",
    )
    p.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for all workers (default: stealth)",
    )
    p.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Base Chrome profile to sync from (default: system)",
    )


def _add_bibtex_process_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--bibtex",
        type=str,
        required=True,
        help="Path to BibTeX file",
        metavar="FILE",
    )
    p.add_argument(
        "--project",
        type=str,
        help="Project name for organizing papers",
        metavar="NAME",
    )
    p.add_argument(
        "--output",
        type=str,
        help="Output path for enriched BibTeX (default: {input}_processed.bib)",
        metavar="FILE",
    )
    p.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
        metavar="N",
    )
    p.add_argument(
        "--browser-mode",
        type=str,
        choices=["stealth", "interactive"],
        default="stealth",
        help="Browser mode for all workers (default: stealth)",
    )
    p.add_argument(
        "--chrome-profile",
        type=str,
        default="system",
        help="Base Chrome profile to sync from (default: system)",
    )


def _add_mcp_subparsers(mcp_parser: argparse.ArgumentParser) -> None:
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


# ---------------------------------------------------------------------------
# Builders that wire shared subparsers into either a new-style group or the
# deprecated top-level alias.
# ---------------------------------------------------------------------------


def _add_pdf_highlight_args(p: argparse.ArgumentParser) -> None:
    """Wire the PDF-highlight CLI's argument list onto the given parser."""
    from .pdf_highlight._cli import build_parser as _build_highlight_parser

    _build_highlight_parser(p)


def _add_library_link_project_tree_args(p: argparse.ArgumentParser) -> None:
    from pathlib import Path

    p.add_argument("project_dir", type=Path, help="Project root directory")
    p.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing symlink or directory at the link path",
    )


def _add_library_materialize_args(p: argparse.ArgumentParser) -> None:
    from pathlib import Path

    p.add_argument("link_path", type=Path, help="Path to the library symlink")
    p.add_argument(
        "--bib",
        type=Path,
        required=True,
        help="BibTeX file whose DOIs select the papers to copy",
    )


def _add_library_dematerialize_args(p: argparse.ArgumentParser) -> None:
    from pathlib import Path

    p.add_argument("path", type=Path, help="Path to the materialized directory")
    p.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Symlink target (default: ~/.scitex/scholar/library)",
    )


def _add_library_db_subparsers(db_parser: argparse.ArgumentParser) -> None:
    """Wire the db sub-subcommands onto the given parser.

    Mirrors the original ``register_subparser`` body in
    ``scitex_scholar.cli._library_index`` but takes the parser as input so the
    new ``library db`` and the deprecated top-level ``db`` can share it.
    """
    from pathlib import Path

    sub = db_parser.add_subparsers(dest="db_command", required=True)

    b = sub.add_parser("build", help="(Re)build the index from MASTER metadata")
    b.add_argument(
        "--library-root",
        type=Path,
        default=None,
        help="Defaults to ~/.scitex/scholar/library",
    )
    b.add_argument("--verbose", action="store_true")

    m = sub.add_parser("migrate", help="Apply pending schema migrations")
    m.add_argument("--library-root", type=Path, default=None)

    lu = sub.add_parser("lookup", help="Fetch a paper by DOI or paper_id")
    lu.add_argument("--library-root", type=Path, default=None)
    g = lu.add_mutually_exclusive_group(required=True)
    g.add_argument("--doi")
    g.add_argument("--paper-id")

    ls = sub.add_parser("list", help="List indexed papers")
    ls.add_argument("--library-root", type=Path, default=None)
    ls.add_argument("--limit", type=int, default=20)
    ls.add_argument("--offset", type=int, default=0)

    de = sub.add_parser(
        "dedupe",
        help="Resolve duplicate-DOI entries (quarantine losers)",
        description=(
            "Detect duplicate-DOI groups in MASTER and pick a winner per "
            "group by a scored rubric (PDF presence, populated metadata, "
            "citation count, mtime). Default is dry-run — pass --apply "
            "to move losers to MASTER_quarantine/ (reversible). "
            "--hard-delete removes losers instead of quarantining."
        ),
    )
    de.add_argument("--library-root", type=Path, default=None)
    de.add_argument(
        "--apply",
        action="store_true",
        help="Execute the plan (default is dry-run)",
    )
    de.add_argument(
        "--hard-delete",
        action="store_true",
        help="Delete losers instead of quarantining (irreversible)",
    )

    au = sub.add_parser(
        "audit",
        help="Report library anomalies without raising (read-only)",
        description=(
            "Walk MASTER and decorated symlinks, report duplicate DOIs, "
            "unparseable metadata, missing PDFs, and orphaned symlinks. "
            "Always exits 0 unless --strict is passed."
        ),
    )
    au.add_argument("--library-root", type=Path, default=None)
    au.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit JSON instead of human-readable text",
    )
    au.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any issue is found (for CI)",
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def create_parser() -> argparse.ArgumentParser:
    """Create main argument parser with noun-verb subcommand groups + deprecation aliases."""
    parser = argparse.ArgumentParser(
        prog="scitex-scholar",
        description="""
SciTeX Scholar - Scientific Literature Management
═════════════════════════════════════════════════

Noun-verb subcommand groups:
  paper   {fetch, fetch-batch}                       — fetch paper(s) into the library
  bibtex  {import}                                   — import a BibTeX file
  pdf     {highlight}                                — PDF post-processing
  library {link-project-tree, materialize, dematerialize, db}
                                                     — library-tree management
  mcp     {start, list-tools, doctor, install}       — MCP server

STORAGE: ~/.scitex/scholar/library/
  MASTER/{8DIGITID}/  — Centralized storage (no duplicates)
  {project}/          — Project symlinks to MASTER
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=False,
    )

    # ========================================
    # Group: paper
    # ========================================
    paper_parser = subparsers.add_parser(
        "paper",
        help="Operate on a paper / batch of papers",
        description="Paper-level operations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    paper_sub = paper_parser.add_subparsers(dest="paper_command", required=False)

    pp = paper_sub.add_parser(
        "fetch",
        help="Fetch a single paper into the library",
        description="Resolve, enrich, download, and save a paper from DOI or title.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_paper_process_args(pp)

    pb = paper_sub.add_parser(
        "fetch-batch",
        help="Fetch multiple papers in parallel",
        description="Parallel multi-worker variant of `paper fetch` (DOIs, titles, or both).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_paper_batch_args(pb)

    # ========================================
    # Group: bibtex
    # ========================================
    bibtex_parser = subparsers.add_parser(
        "bibtex",
        help="Operate on a BibTeX file",
        description="BibTeX-file-level operations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bibtex_sub = bibtex_parser.add_subparsers(dest="bibtex_command", required=False)

    bp = bibtex_sub.add_parser(
        "import",
        help="Import & enrich all papers from a BibTeX file",
        description="Resolve DOIs, enrich metadata, and download PDFs for every entry in a BibTeX file (parallel workers).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_bibtex_process_args(bp)

    # NOTE: ``bibtex`` doubles as the new noun group AND as the deprecation
    # alias for the old top-level form. The old form ``bibtex --bibtex …``
    # is rewritten to ``bibtex process --bibtex …`` in :func:`_rewrite_argv`
    # before parsing, so we don't need to pollute the group parser with
    # ``--bibtex`` and friends.

    # ========================================
    # Group: mcp (already noun-verb-ish, kept as-is)
    # ========================================
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP (Model Context Protocol) server commands",
        description="MCP (Model Context Protocol) server commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_mcp_subparsers(mcp_parser)

    # ========================================
    # Group: pdf
    # ========================================
    pdf_parser = subparsers.add_parser(
        "pdf",
        help="PDF post-processing",
        description="PDF-level operations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pdf_sub = pdf_parser.add_subparsers(dest="pdf_command", required=False)

    ph = pdf_sub.add_parser(
        "highlight",
        help="Overlay semantic highlights on a PDF",
        description=(
            "Tag each paragraph of a PDF with a rhetorical role "
            "(claim/method/limitation/supportive/contradictive) via Claude, "
            "then write a copy with colour-coded highlight annotations."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_pdf_highlight_args(ph)

    # ========================================
    # Group: library
    # ========================================
    library_parser = subparsers.add_parser(
        "library",
        help="Library-tree management",
        description="Library-tree operations: link, materialize, dematerialize, db.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    library_sub = library_parser.add_subparsers(dest="library_command", required=False)

    lpt = library_sub.add_parser(
        "link-project-tree",
        help="Symlink a project's .scitex/scholar/library to the home library",
        description=(
            "Create <dir>/.scitex/scholar/library → ~/.scitex/scholar/library/. "
            "Idempotent. Use --force to replace a differing target."
        ),
    )
    _add_library_link_project_tree_args(lpt)

    lmat = library_sub.add_parser(
        "materialize",
        help="Replace a library-symlink with a bib-filtered real directory",
        description=(
            "Replace the symlink at <link_path> with a real directory "
            "containing MASTER/<paper_id>/ subtrees for each DOI cited "
            "in <bib>. Useful for shipping a self-contained project tarball."
        ),
    )
    _add_library_materialize_args(lmat)

    ldemat = library_sub.add_parser(
        "dematerialize",
        help="Replace a materialized library directory with a symlink",
        description=(
            "Delete the real directory at <path> and replace it with a "
            "symlink to the user's home library (or --target)."
        ),
    )
    _add_library_dematerialize_args(ldemat)

    ldb = library_sub.add_parser(
        "db",
        help="Manage the library SQLite index",
        description=(
            "Build / migrate / query the library index at <library_root>/index.db."
        ),
    )
    _add_library_db_subparsers(ldb)

    # ========================================
    # Deprecation aliases (top-level)
    # ========================================
    # Hidden from --help (help=argparse.SUPPRESS). Still parse correctly so
    # existing scripts keep working; they just emit a DeprecationWarning at
    # invocation time. To be removed in 1.4.0.
    single_alias = subparsers.add_parser(
        "single",
        help=argparse.SUPPRESS,
        description="DEPRECATED: alias for `paper fetch`. Will be removed in 1.4.0.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_paper_process_args(single_alias)

    parallel_alias = subparsers.add_parser(
        "parallel",
        help=argparse.SUPPRESS,
        description="DEPRECATED: alias for `paper fetch-batch`. Will be removed in 1.4.0.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_paper_batch_args(parallel_alias)

    # ``bibtex`` already doubles as both new group and old alias — see above.

    highlight_alias = subparsers.add_parser(
        "highlight",
        help=argparse.SUPPRESS,
        description=(
            "DEPRECATED: alias for `pdf highlight`. Will be removed in 1.4.0."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_pdf_highlight_args(highlight_alias)

    lpt_alias = subparsers.add_parser(
        "link-project-tree",
        help=argparse.SUPPRESS,
        description=(
            "DEPRECATED: alias for `library link-project-tree`. "
            "Will be removed in 1.4.0."
        ),
    )
    _add_library_link_project_tree_args(lpt_alias)

    mat_alias = subparsers.add_parser(
        "materialize",
        help=argparse.SUPPRESS,
        description=(
            "DEPRECATED: alias for `library materialize`. Will be removed in 1.4.0."
        ),
    )
    _add_library_materialize_args(mat_alias)

    demat_alias = subparsers.add_parser(
        "dematerialize",
        help=argparse.SUPPRESS,
        description=(
            "DEPRECATED: alias for `library dematerialize`. Will be removed in 1.4.0."
        ),
    )
    _add_library_dematerialize_args(demat_alias)

    db_alias = subparsers.add_parser(
        "db",
        help=argparse.SUPPRESS,
        description=("DEPRECATED: alias for `library db`. Will be removed in 1.4.0."),
    )
    _add_library_db_subparsers(db_alias)

    # `argparse` shows ``help=SUPPRESS`` rows as literal "==SUPPRESS==". To
    # actually hide deprecated rows from the top-level command list, drop
    # them from ``_choices_actions`` (the formatter's row source).
    _deprecated_top_level = {
        "single",
        "parallel",
        "highlight",
        "link-project-tree",
        "materialize",
        "dematerialize",
        "db",
    }
    subparsers._choices_actions = [
        a for a in subparsers._choices_actions if a.dest not in _deprecated_top_level
    ]

    return parser


# ---------------------------------------------------------------------------
# Handlers (one per logical operation, shared between new + deprecated forms)
# ---------------------------------------------------------------------------


async def run_paper_process(args) -> int:
    """Run single paper pipeline."""
    from .pipelines.ScholarPipelineSingle import ScholarPipelineSingle

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


async def run_paper_batch(args) -> int:
    """Run parallel papers pipeline."""
    from .pipelines.ScholarPipelineParallel import ScholarPipelineParallel

    if not args.dois and not args.titles:
        logger.error("Either --dois or --titles is required")
        return 1

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


async def run_bibtex_process(args) -> int:
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


async def run_mcp_server() -> int:
    """Run MCP server."""
    from .mcp_server import main as mcp_main

    logger.info("Starting Scholar MCP server...")
    import inspect
    from typing import Any, cast

    result: Any = mcp_main()
    if inspect.isawaitable(result):
        await cast(Any, result)
    return 0


def run_pdf_highlight(args) -> int:
    from .pdf_highlight._cli import run as _run_highlight

    return _run_highlight(args)


def run_library_link_project_tree(args) -> int:
    from .cli._project_tree import run as _run

    return _run(args)


def run_library_materialize(args) -> int:
    from .cli._materialize import run_materialize as _run

    return _run(args)


def run_library_dematerialize(args) -> int:
    from .cli._materialize import run_dematerialize as _run

    return _run(args)


def run_library_db(args) -> int:
    from .cli._library_index import run as _run

    return _run(args)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _warn_deprecated(old_form: str, new_form: str) -> None:
    print(
        f"DeprecationWarning: 'scitex-scholar {old_form}' is deprecated; "
        f"use 'scitex-scholar {new_form}' (will be removed in 1.4.0).",
        file=sys.stderr,
    )


def _rewrite_argv_for_bibtex_alias(argv: list[str]) -> tuple[list[str], bool]:
    """Pre-process argv to support the deprecated ``bibtex --bibtex …`` form.

    The new noun-verb shape is ``bibtex process --bibtex …``. To keep the old
    shape working without polluting the group parser, we look for ``bibtex``
    at the top level followed by something that's not a known sub-verb or a
    help flag. If matched, we inject ``process`` after ``bibtex`` and signal
    that a deprecation warning should be emitted.

    Returns ``(rewritten_argv, was_rewritten)``.
    """
    if len(argv) < 2 or argv[0] != "bibtex":
        return argv, False
    next_token = argv[1]
    known_subs = {"import", "-h", "--help"}
    if next_token in known_subs:
        return argv, False
    # Looks like the deprecated form — inject ``import``.
    return [argv[0], "import", *argv[1:]], True


async def main_async(argv: list[str] | None = None) -> int:
    """Main async entry point."""
    parser = create_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]

    bibtex_alias_used = False
    if raw and raw[0] == "bibtex":
        rewritten, bibtex_alias_used = _rewrite_argv_for_bibtex_alias(raw)
        raw = rewritten

    args = parser.parse_args(raw)
    if bibtex_alias_used:
        _warn_deprecated("bibtex --bibtex …", "bibtex import --bibtex …")

    # No subcommand: print help to stdout and exit 0
    if args.command is None:
        parser.print_help()
        return 0

    cmd = args.command

    # ----- New noun-verb groups -----
    if cmd == "paper":
        sub = getattr(args, "paper_command", None)
        if sub == "fetch":
            return await run_paper_process(args)
        if sub == "fetch-batch":
            return await run_paper_batch(args)
        # bare `scitex-scholar paper`
        parser.parse_args(["paper", "--help"])  # exits
        return 0

    if cmd == "bibtex":
        sub = getattr(args, "bibtex_command", None)
        if sub == "import":
            return await run_bibtex_process(args)
        parser.parse_args(["bibtex", "--help"])  # exits
        return 0

    if cmd == "mcp":
        from .cli._mcp_commands import run_mcp_subcommand

        return await run_mcp_subcommand(args, run_server=run_mcp_server)

    if cmd == "pdf":
        sub = getattr(args, "pdf_command", None)
        if sub == "highlight":
            return run_pdf_highlight(args)
        parser.parse_args(["pdf", "--help"])  # exits
        return 0

    if cmd == "library":
        sub = getattr(args, "library_command", None)
        if sub == "link-project-tree":
            return run_library_link_project_tree(args)
        if sub == "materialize":
            return run_library_materialize(args)
        if sub == "dematerialize":
            return run_library_dematerialize(args)
        if sub == "db":
            return run_library_db(args)
        parser.parse_args(["library", "--help"])  # exits
        return 0

    # ----- Deprecation aliases -----
    if cmd == "single":
        _warn_deprecated("single", "paper fetch")
        return await run_paper_process(args)
    if cmd == "parallel":
        _warn_deprecated("parallel", "paper fetch-batch")
        return await run_paper_batch(args)
    if cmd == "highlight":
        _warn_deprecated("highlight", "pdf highlight")
        return run_pdf_highlight(args)
    if cmd == "link-project-tree":
        _warn_deprecated("link-project-tree", "library link-project-tree")
        return run_library_link_project_tree(args)
    if cmd == "materialize":
        _warn_deprecated("materialize", "library materialize")
        return run_library_materialize(args)
    if cmd == "dematerialize":
        _warn_deprecated("dematerialize", "library dematerialize")
        return run_library_dematerialize(args)
    if cmd == "db":
        _warn_deprecated("db", "library db")
        return run_library_db(args)

    logger.error(f"Unknown command: {cmd}")
    return 1


def main() -> int:
    """Synchronous entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())


# EOF
