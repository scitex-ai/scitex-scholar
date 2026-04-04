#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: "2025-08-16 23:56:08 (ywatanabe)"
# File: /home/ywatanabe/proj/SciTeX-Code/src/scitex/scholar/cli/download_pdf.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = __file__
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

"""Command-line interface for paywalled PDF downloads.

Usage:
    python -m scitex_scholar.download bibtex <file.bib> [--project NAME]
    python -m scitex_scholar.download paper --doi <DOI> [--title TITLE]
    python -m scitex_scholar.download paper --url <URL>
    python -m scitex_scholar.download info
"""

import argparse
import sys

from scitex import logging
from scitex_scholar.core import Paper
from scitex_scholar.pdf_download.ScholarPDFDownloader import ScholarPDFDownloader

logger = logging.getLogger(__name__)


def create_parser():
    """Create argument parser for download_pdf command."""
    parser = argparse.ArgumentParser(
        description="Download PDFs from paywalled journals using institutional authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
# Download PDFs from BibTeX file
python -m scitex.scholar download bibtex pac.bib --project myproject

# Download single paper by DOI
python -m scitex.scholar download paper --doi 10.1038/nature12345

# Download single paper by URL
python -m scitex.scholar download paper --url https://www.nature.com/articles/nature12345

# Show system info
python -m scitex.scholar download info""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # BibTeX command
    bibtex_parser = subparsers.add_parser(
        "bibtex", help="Download PDFs from BibTeX file"
    )
    bibtex_parser.add_argument("file", help="BibTeX file path")
    bibtex_parser.add_argument(
        "--project",
        default="default",
        help="Project name for organization (default: default)",
    )
    bibtex_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent downloads (default: 3)",
    )

    # Paper command
    paper_parser = subparsers.add_parser("paper", help="Download single paper")
    paper_group = paper_parser.add_mutually_exclusive_group(required=True)
    paper_group.add_argument("--doi", help="DOI of the paper")
    paper_group.add_argument("--url", help="URL of the paper")
    paper_parser.add_argument("--title", help="Paper title (for DOI-based downloads)")
    paper_parser.add_argument(
        "--project",
        default="default",
        help="Project name for organization (default: default)",
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Show system information")

    return parser


def main():
    """Main entry point for paywalled PDF download CLI."""
    parser = create_parser()

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "bibtex":
        from pathlib import Path

        from scitex_scholar import Scholar

        bibtex_path = Path(args.file)
        if not bibtex_path.exists():
            print(f"Error: BibTeX file not found: {bibtex_path}")
            return 1

        print(f"\n🎯 SciTeX Scholar - PDF Downloader")
        print(f"📄 Processing: {bibtex_path}")
        print(f"🏢 Project: {args.project}")
        print(f"🔐 Using institutional authentication")

        try:
            # Use Scholar interface
            scholar = Scholar(project=args.project)

            # Set up output directory
            output_dir = Path(f"/tmp/scholar_downloads/{args.project}/")
            output_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n⬇️  Starting downloads...")
            print(f"📁 Output directory: {output_dir}")

            # Download PDFs using Scholar interface - it handles loading and DOI extraction
            results = scholar.download_pdfs_from_bibtex(bibtex_path, output_dir)

            print(f"\n✅ Downloaded: {results['downloaded']} PDFs")
            print(f"❌ Failed: {results['failed']}")
            if results.get("errors"):
                print(f"⚠️  Errors: {results['errors']}")

            return 0

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
            return 1

    elif args.command == "paper":
        import asyncio

        async def download_paper_async(args):
            from scitex_scholar import (
                ScholarAuthManager,
                ScholarBrowserManager,
                ScholarConfig,
            )

            # Create paper object with Pydantic structure
            paper = Paper()
            paper.metadata.basic.title = args.title or "Unknown"
            if args.doi:
                paper.metadata.set_doi(args.doi)
            if args.url:
                paper.metadata.url.publisher = args.url

            print(f"\n🎯 SciTeX Scholar - Paywalled PDF Downloader")
            print(f"📄 Paper: {paper.metadata.basic.title}")
            print(f"🔗 {'DOI' if args.doi else 'URL'}: {args.doi or args.url}")
            print(f"🏢 Project: {args.project}")
            print(f"🔐 Using institutional authentication")

            try:
                # Set up browser with authentication
                browser_manager = ScholarBrowserManager(
                    chrome_profile_name="system",
                    browser_mode="stealth",
                    auth_manager=ScholarAuthManager(),
                    use_zenrows_proxy=False,
                )
                (
                    browser,
                    context,
                ) = await browser_manager.get_authenticated_browser_and_context_async()

                # Create downloader with authenticated context
                downloader = ScholarPDFDownloader(context, config=ScholarConfig())

                # Download based on DOI or URL
                if args.doi:
                    saved_paths = await downloader.download_from_doi(
                        args.doi, output_dir=f"/tmp/scholar_downloads/{args.project}/"
                    )
                    success = bool(saved_paths)
                    pdf_path = saved_paths[0] if saved_paths else None
                else:
                    title = paper.metadata.basic.title or "untitled"
                    pdf_path = await downloader.download_from_url(
                        args.url,
                        output_path=f"/tmp/scholar_downloads/{args.project}/{title[:30]}.pdf",
                    )
                    success = bool(pdf_path)

                if success and pdf_path:
                    print(f"\n✅ Downloaded successfully: {pdf_path}")
                else:
                    print(f"\n❌ Download failed")

                await browser.close()
                return 0 if success else 1

            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback

                traceback.print_exc()
                return 1

        return asyncio.run(download_paper_async(args))

    elif args.command == "info":
        print(f"\n🎯 SciTeX Scholar - Paywalled PDF Downloader")
        print(f"=" * 50)
        print(f"Strategy: Institutional Authentication + Stealth Browser")
        print(f"Focus: Paywalled academic content")
        print(f"Authentication: OpenAthens/University credentials")
        print(f"Extensions: Accept Cookies, Zotero Connector")
        print(f"Zotero Translators: Enabled")
        print(f"=" * 50)
        print(f"\n💡 This tool specializes in accessing paywalled academic content")
        print(f"   that requires institutional authentication.")
        print(f"\n🏆 Competitive Advantage: Access content others can't reach!")
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

# EOF
