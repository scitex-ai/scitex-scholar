#!/usr/bin/env python3
# Timestamp: "2026-01-14 (ywatanabe)"
# File: src/scitex/scholar/pipelines/_single_steps.py
"""Step implementations for ScholarPipelineSingle."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import scitex_logging as logging

from scitex_scholar.core import Paper

if TYPE_CHECKING:
    from scitex_scholar.storage import PaperIO

logger = logging.getLogger(__name__)


class PipelineStepsMixin:
    """Mixin containing step implementations for single paper pipeline."""

    # ----------------------------------------
    # Steps
    # ----------------------------------------
    def _step_01_normalize_as_doi(self, doi_or_title):
        """Accept bare DOIs and DOI-bearing URLs.

        Examples that all normalize to ``10.1002/epi.70076``:
          • ``10.1002/epi.70076``
          • ``doi:10.1002/epi.70076``
          • ``https://doi.org/10.1002/epi.70076``
          • ``http://dx.doi.org/10.1002/epi.70076``
          • ``https://www.doi.org/10.1002/epi.70076``
        Anything else returns ``None`` (treated as a title query).
        """
        logger.info(f"{self.name}: Processing Query: {doi_or_title}")
        s = (doi_or_title or "").strip()
        if not s:
            return None

        if s.lower().startswith("doi:"):
            s = s[4:].strip()

        if s.lower().startswith(("http://", "https://")):
            # Look for "doi.org/<DOI>" anywhere in the URL.
            for marker in ("doi.org/", "dx.doi.org/"):
                idx = s.lower().find(marker)
                if idx >= 0:
                    s = s[idx + len(marker) :]
                    break
            else:
                # Not a DOI URL — treat as title.
                return None
            # Trim query/fragment.
            s = s.split("?")[0].split("#")[0]

        return s if s.startswith("10.") else None

    async def _step_02_create_paper(self, doi, doi_or_title):
        """Create Paper object and resolve DOI from title if needed."""
        paper = Paper()
        if doi:
            paper.metadata.id.doi = doi
            paper.metadata.id.doi_engines = ["user_input"]
        else:
            from scitex_scholar.metadata_engines import ScholarEngine

            engine = ScholarEngine()
            metadata_dict = await engine.search_async(title=doi_or_title)
            if metadata_dict and metadata_dict.get("id", {}).get("doi"):
                doi = metadata_dict["id"]["doi"]
                paper.metadata.id.doi = doi
                paper.metadata.id.doi_engines = metadata_dict["id"].get(
                    "doi_engines", ["ScholarEngine"]
                )
                logger.success(f"{self.name}: DOI resolved from title: {doi}")
                self._merge_metadata_into_paper(paper, metadata_dict)
            else:
                logger.error(f"{self.name}: Could not resolve DOI: {doi_or_title}")
                raise ValueError(f"No DOI found for title: {doi_or_title}")
        return paper

    def _step_03_add_paper_id(self, paper):
        paper_id = self._generate_paper_id(paper.metadata.id.doi)
        paper.container.library_id = paper_id
        logger.info(f"{self.name}: Library ID: {paper_id}")
        return paper

    async def _step_04_resolve_metadata(self, paper, io, force):
        if not io.has_metadata() or force:
            logger.info(f"{self.name}: Resolving metadata...")
            from scitex_scholar.metadata_engines import ScholarEngine

            engine = ScholarEngine()
            metadata_dict = await engine.search_async(doi=paper.metadata.id.doi)
            if metadata_dict:
                self._merge_metadata_into_paper(paper, metadata_dict)
                self._enrich_impact_factor(paper)
                io.save_metadata()
                logger.success(f"{self.name}: Metadata enriched")
            else:
                paper.metadata.basic.title = "Pending metadata resolution"
                paper.metadata.basic.title_engines = ["pending"]
                io.save_metadata()
                logger.warning(f"{self.name}: No metadata found")
        else:
            logger.info(f"{self.name}: Metadata exists, loading...")
            paper = io.load_metadata()
            if paper.metadata.basic.title == "Pending metadata resolution":
                logger.info(f"{self.name}: Enriching existing metadata...")
                from scitex_scholar.metadata_engines import ScholarEngine

                engine = ScholarEngine()
                metadata_dict = await engine.search_async(doi=paper.metadata.id.doi)
                if metadata_dict:
                    self._merge_metadata_into_paper(paper, metadata_dict)
                    self._enrich_impact_factor(paper)
                    io.save_metadata()
                    logger.success(f"{self.name}: Metadata enriched")
        return paper

    async def _step_05_setup_browser(self, paper, io):
        needs_browser = not paper.metadata.url.pdfs or not io.has_pdf()
        if not needs_browser:
            return None, None, None
        from scitex_scholar import ScholarAuthManager, ScholarBrowserManager
        from scitex_scholar.auth import AuthenticationGateway

        logger.info(f"{self.name}: Setting up browser ({self.chrome_profile})...")
        auth_manager = ScholarAuthManager()
        browser_manager = ScholarBrowserManager(
            chrome_profile_name=self.chrome_profile,
            browser_mode=self.browser_mode,
            auth_manager=auth_manager,
        )
        (
            browser,
            context,
        ) = await browser_manager.get_authenticated_browser_and_context_async()
        auth_gateway = AuthenticationGateway(
            auth_manager=auth_manager, browser_manager=browser_manager
        )
        return browser_manager, context, auth_gateway

    async def _step_06_find_pdf_urls(
        self, paper, io, context, auth_gateway, force, browser_manager=None
    ):
        if not paper.metadata.url.pdfs or force:
            logger.info(f"{self.name}: Finding PDF URLs...")
            try:
                url_context = await auth_gateway.prepare_context_async(
                    doi=paper.metadata.id.doi, context=context
                )
                publisher_url = (
                    url_context.url if url_context else paper.metadata.id.doi
                )
            except Exception as e:
                logger.warning(f"{self.name}: Auth gateway failed: {e}")
                await self._capture_screenshot(
                    browser_manager, context, io, "auth_gateway_failed"
                )
                publisher_url = paper.metadata.id.doi
            from scitex_scholar import ScholarURLFinder

            url_finder = ScholarURLFinder(context)
            urls = await url_finder.find_pdf_urls(publisher_url)
            paper.metadata.url.pdfs = urls
            paper.metadata.url.pdfs_engines = ["ScholarURLFinder"]
            if not urls:
                from datetime import datetime, timezone

                paper.metadata.access.pdf_download_attempted_at = datetime.now(
                    timezone.utc
                ).isoformat()
                paper.metadata.access.pdf_download_status = "no_urls"
                paper.metadata.access.pdf_download_error = (
                    f"No PDF URLs found at {publisher_url}"
                )
                await self._capture_screenshot(
                    browser_manager, context, io, "no_pdf_urls_found"
                )
            io.save_metadata()
            logger.info(f"{self.name}: Found {len(urls)} PDF URL(s)")
        else:
            logger.info(f"{self.name}: PDF URLs exist ({len(paper.metadata.url.pdfs)})")

    async def _step_07_download_pdf(
        self, paper, io, context, auth_gateway, force, browser_manager=None
    ):
        if (not io.has_pdf() or force) and paper.metadata.url.pdfs:
            logger.info(f"{self.name}: Downloading PDF...")
            from scitex_scholar.pdf_download import ScholarPDFDownloader

            # Pre-download landing page capture. The Chrome PDF Viewer
            # strategy can close the browser context on Cloudflare
            # challenges, so capturing BEFORE the risky step guarantees
            # we keep a visual record even when the page is later lost.
            await self._capture_screenshot(
                browser_manager, context, io, "pre_download_landing"
            )
            downloader = ScholarPDFDownloader(context)
            downloaded, temp_path, download_method = await self._download_pdf_from_url(
                paper, io, context, auth_gateway, downloader
            )
            if downloaded:
                self._handle_downloaded_pdf(
                    paper, io, downloaded, temp_path, download_method
                )
            else:
                await self._capture_screenshot(
                    browser_manager, context, io, "pdf_download_failed"
                )
                self._check_manual_download(io, paper)
        elif io.has_pdf():
            logger.info(f"{self.name}: PDF already exists, skipping download")

    def _step_07_import_pdf(self, paper, io, pdf_path, force):
        """Back-compat shim: single main-PDF import. Delegates to the
        general :meth:`_step_07_import_files`.
        """
        self._step_07_import_files(
            paper,
            io,
            pdf_main=pdf_path,
            pdf_supples=(),
            attachments=(),
            force=force,
        )

    def _step_07_import_files(
        self, paper, io, *, pdf_main, pdf_supples, attachments, force
    ):
        """Place user-provided files into MASTER and record them.

        Roles and on-disk naming (flat layout, prefix-encoded):
          * ``pdf_main``    → ``MASTER/<id>/<First>-<Year>-<Journal>.pdf``
          * ``pdf_supples`` → ``MASTER/<id>/supple-<original_name>``
          * ``attachments`` → ``MASTER/<id>/additional-<original_name>``

        Each placement is recorded in ``metadata.path.files`` as a dict
        with ``{role, name, sha256, size, added_at, source}`` so the role
        survives later renames; legacy list-of-strings fields
        (``metadata.path.pdfs`` / ``supplementary_files`` /
        ``additional_files``) are kept in sync for back-compat readers.
        """
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()

        files_list = list(getattr(paper.metadata.path, "files", []) or [])

        if pdf_main:
            entry = self._import_one_file(io, pdf_main, role="main", force=force, ts=ts)
            if entry:
                files_list.append(entry)
                paper.metadata.path.pdfs = [str(io.get_pdf_path())]
                paper.metadata.path.pdfs_engines = ["manual_import"]
                paper.metadata.access.pdf_download_attempted_at = ts
                paper.metadata.access.pdf_download_status = "success"
                paper.metadata.access.pdf_download_error = None
                try:
                    paper.container.pdf_size_bytes = io.get_pdf_path().stat().st_size
                except OSError:
                    pass
                self._check_doi_sanity(paper, io.get_pdf_path())

        supple_paths = []
        for s in pdf_supples or ():
            entry = self._import_one_file(
                io, s, role="supplementary", force=force, ts=ts
            )
            if entry:
                files_list.append(entry)
                supple_paths.append(entry["name"])
        if supple_paths:
            existing = list(paper.metadata.path.supplementary_files or [])
            paper.metadata.path.supplementary_files = existing + supple_paths

        attach_paths = []
        for a in attachments or ():
            entry = self._import_one_file(io, a, role="additional", force=force, ts=ts)
            if entry:
                files_list.append(entry)
                attach_paths.append(entry["name"])
        if attach_paths:
            existing = list(paper.metadata.path.additional_files or [])
            paper.metadata.path.additional_files = existing + attach_paths

        try:
            paper.metadata.path.files = files_list
        except Exception:
            pass

        io.save_metadata()
        if pdf_main or pdf_supples or attachments:
            logger.success(
                f"{self.name}: imported "
                f"main={'1' if pdf_main else '0'} "
                f"supple={len(pdf_supples or ())} "
                f"attachments={len(attachments or ())}"
            )

    def _import_one_file(self, io, src_path, *, role, force, ts):
        """Copy one file into ``io.paper_dir`` under the role-prefixed name.

        Returns the structured ``files`` entry dict on success, ``None`` on
        skip/missing.
        """
        import hashlib
        import shutil
        from pathlib import Path as _Path

        src = _Path(src_path).expanduser().resolve()
        if not src.exists():
            logger.fail(f"{self.name}: missing source: {src}")
            return None

        if role == "main":
            dest = io.get_pdf_path()
            display_name = dest.name
        else:
            prefix = "supple-" if role == "supplementary" else "additional-"
            base = src.name
            if not base.startswith(prefix):
                base = f"{prefix}{base}"
            dest = io.paper_dir / base
            display_name = base

        if dest.exists() and not force:
            logger.info(
                f"{self.name}: skip ({role}) — exists: {dest.name} "
                "(--force to overwrite)"
            )
            return None

        shutil.copy2(str(src), str(dest))
        size = dest.stat().st_size
        h = hashlib.sha256()
        with open(dest, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)

        # Zotero pattern: keep the canonical record-of-paper file
        # immutable. Annotations live in separate files (notes-*.pdf,
        # annotations/*.json). chmod 444 makes accidental "save" via a
        # PDF reader fail loudly instead of silently drifting.
        if role == "main":
            try:
                import os
                import stat

                os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError as exc:
                logger.debug(f"{self.name}: could not chmod 444 {dest.name}: {exc}")

        return {
            "role": role,
            "name": display_name,
            "sha256": h.hexdigest(),
            "size": size,
            "added_at": ts,
            "source": str(src),
            "immutable": role == "main",
        }

    def _check_doi_sanity(self, paper, pdf_path):
        """Warn if the main PDF's page-1 DOI disagrees with metadata.id.doi.

        Cheap defense against the kind of swap we saw with Maturana/Karoly.
        """
        try:
            import re

            from pypdf import PdfReader

            text = (PdfReader(str(pdf_path)).pages[0].extract_text()) or ""
        except Exception:
            return
        m = re.search(r"10\.\d{4,}/\S+", text)
        if not m:
            return
        pdf_doi = m.group().rstrip(".,;)").lower()
        meta_doi = (paper.metadata.id.doi or "").lower()
        if not meta_doi:
            return
        if meta_doi not in pdf_doi and pdf_doi not in meta_doi:
            logger.warning(
                f"{self.name}: DOI MISMATCH on {pdf_path.name}: "
                f"metadata={meta_doi!r} vs PDF page-1={pdf_doi!r}"
            )

    def _step_08_extract_content(self, io, force):
        if io.has_pdf() and (not io.has_content() or force):
            logger.info(f"{self.name}: Extracting content (text, tables, images)...")
            import scitex_io

            try:
                pdf_path = io.get_pdf_path()
                content = scitex_io.load(
                    str(pdf_path),
                    ext="pdf",
                    mode="scientific",
                    output_dir=str(io.get_images_dir()),
                )
                if hasattr(content, "text") and content.text:
                    io.save_text(content.text)
                if hasattr(content, "tables") and content.tables:
                    io.save_tables_from_extraction(content.tables)
                stats = getattr(content, "stats", {})
                logger.info(
                    f"{self.name}: Extracted {stats.get('num_tables', 0)} tables, "
                    f"{stats.get('num_images', 0)} images"
                )
            except Exception as e:
                logger.warning(f"{self.name}: Content extraction failed: {e}")

    def _step_09_link_to_project(self, paper, io, project):
        if project:
            logger.info(f"{self.name}: Linking to project: {project}")
            return self._link_to_project(paper, project, io)
        return None

    def _step_10_log_final_status(self, io):
        logger.success(f"{self.name}: Complete")
        for filename, exists in io.get_all_files().items():
            logger.debug(f"  {'✓' if exists else '✗'} {filename}")

    # ----------------------------------------
    # Step 07 Helpers
    # ----------------------------------------
    async def _download_pdf_from_url(
        self, paper, io, context, auth_gateway, downloader
    ):
        pdf_url = paper.metadata.url.pdfs[0]
        if isinstance(pdf_url, dict):
            pdf_url = pdf_url["url"]
        logger.info(f"{self.name}: PDF URL: {pdf_url}")
        try:
            await auth_gateway.prepare_context_async(
                doi=paper.metadata.id.doi, context=context
            )
        except Exception as e:
            # Record auth failure in metadata so downstream consumers can
            # distinguish "download failed" from "auth never established".
            from datetime import datetime, timezone

            paper.metadata.access.pdf_download_attempted_at = datetime.now(
                timezone.utc
            ).isoformat()
            paper.metadata.access.pdf_download_status = "auth_failed"
            paper.metadata.access.pdf_download_error = (
                f"auth_gateway.prepare_context_async: {type(e).__name__}: {e}"
            )
            logger.warning(
                f"{self.name}: Auth gateway failed before download: {e}",
                exc_info=True,
            )
        # Unique temp path so concurrent runs on the same paper don't collide.
        import uuid

        temp_pdf_path = io.paper_dir / f"temp-{uuid.uuid4().hex[:8]}.pdf"
        downloaded_file = await downloader.download_from_url(
            pdf_url, output_path=temp_pdf_path, doi=paper.metadata.id.doi
        )
        # Track download method based on context flags
        download_method = "unknown"
        if downloaded_file:
            is_manual = getattr(context, "_scitex_is_manual_mode", False)
            download_method = "manual_download" if is_manual else "automated"
        return downloaded_file, temp_pdf_path, download_method

    def _handle_downloaded_pdf(
        self, paper, io, downloaded_file, temp_pdf_path, download_method="unknown"
    ):
        import shutil
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        paper.metadata.access.pdf_download_attempted_at = now_iso
        paper.metadata.access.pdf_download_status = "success"
        paper.metadata.access.pdf_download_error = None

        if downloaded_file == temp_pdf_path and temp_pdf_path.exists():
            main_pdf = io.get_pdf_path()
            shutil.move(str(temp_pdf_path), str(main_pdf))
            paper.metadata.path.pdfs = [str(main_pdf)]
            paper.metadata.path.pdfs_engines = [download_method]
            paper.container.pdf_size_bytes = main_pdf.stat().st_size
            io.save_metadata()
            logger.success(
                f"{self.name}: PDF downloaded to MASTER via {download_method}"
            )
        else:
            io.save_pdf(downloaded_file)
            paper.metadata.path.pdfs_engines = [download_method]
            io.save_metadata()
        logger.info(f"{self.name}: PDF saved ({str(downloaded_file)})")

    def _check_manual_download(self, io, paper=None):
        import time

        from scitex_scholar.config import ScholarConfig

        logger.warning(f"{self.name}: Automated download returned None")
        config = ScholarConfig()
        downloads_dir = config.get_library_downloads_dir()
        current_time = time.time()
        recent_pdfs = [
            (p, current_time - p.stat().st_mtime)
            for p in downloads_dir.glob("*")
            if p.is_file()
            and p.stat().st_size > 100_000
            and (current_time - p.stat().st_mtime) < 600
        ]
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        if recent_pdfs:
            recent_pdfs.sort(key=lambda x: x[1])
            latest_pdf = recent_pdfs[0][0]
            logger.info(f"{self.name}: Found recent PDF: {latest_pdf.name}")
            io.save_pdf(latest_pdf)
            if paper:
                paper.metadata.path.pdfs_engines = ["manual_download"]
                paper.metadata.access.pdf_download_attempted_at = now_iso
                paper.metadata.access.pdf_download_status = "success"
                paper.metadata.access.pdf_download_error = None
            io.save_metadata()
            logger.success(f"{self.name}: Manual PDF saved to MASTER")
        else:
            logger.warning(f"{self.name}: No recent PDFs found")
            if paper:
                paper.metadata.access.pdf_download_attempted_at = now_iso
                paper.metadata.access.pdf_download_status = "download_failed"
                paper.metadata.access.pdf_download_error = "Automated download returned None and no fallback PDF in downloads dir"
                io.save_metadata()


class PipelineHelpersMixin:
    """Mixin containing helper methods for single paper pipeline."""

    async def _capture_screenshot(self, browser_manager, context, io, description):
        """Capture screenshot for debugging. Iterates all surviving pages so
        that a closed primary page (common after Cloudflare interstitials)
        still yields a useful artifact."""
        if not browser_manager or not context:
            return
        try:
            from datetime import datetime

            screenshots_dir = io.paper_dir / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                pages = list(context.pages)
            except Exception as e:
                logger.debug(f"{self.name}: cannot enumerate pages: {e}")
                return
            if not pages:
                logger.debug(f"{self.name}: no surviving pages for screenshot")
                return

            saved_any = False
            for idx, page in enumerate(pages):
                suffix = "" if len(pages) == 1 else f"_page{idx}"
                path = screenshots_dir / f"{timestamp}_{description}{suffix}.png"
                try:
                    await browser_manager.take_screenshot_async(
                        page, str(path), full_page=True
                    )
                    logger.info(f"{self.name}: Screenshot saved: {path.name}")
                    saved_any = True
                except Exception as inner:
                    logger.debug(f"{self.name}: screenshot page {idx} failed: {inner}")
                    continue
            if not saved_any:
                logger.debug(f"{self.name}: all pages unreachable for '{description}'")
        except Exception as e:
            logger.debug(f"{self.name}: Screenshot capture failed: {e}")

    def _generate_paper_id(self, doi: str) -> str:
        """Generate 8-digit library ID from DOI."""
        return hashlib.md5(f"DOI:{doi}".encode()).hexdigest()[:8].upper()

    def _link_to_project(
        self, paper: Paper, project: str, io: PaperIO
    ) -> Optional[Path]:
        """Create human-readable symlink in project directory using LibraryManager."""
        from scitex_scholar.storage import LibraryManager

        library_manager = LibraryManager()
        symlink_path = library_manager.update_symlink(
            master_storage_path=io.paper_dir,
            project=project,
        )
        if symlink_path:
            logger.success(
                f"{self.name}: Created symlink: {project}/{symlink_path.name}"
            )
        return symlink_path

    def _enrich_impact_factor(self, paper: Paper) -> None:
        """Add journal impact factor to paper metadata if not present."""
        if paper.metadata.publication.impact_factor:
            return
        journal = (
            paper.metadata.publication.short_journal
            or paper.metadata.publication.journal
        )
        if not journal:
            return
        try:
            from scitex_scholar.impact_factor import ImpactFactorEngine

            if_engine = ImpactFactorEngine()
            metrics = if_engine.get_metrics(journal)
            if metrics and metrics.get("impact_factor"):
                paper.metadata.publication.impact_factor = metrics["impact_factor"]
                paper.metadata.publication.impact_factor_engines = [
                    metrics.get("source", "JCR")
                ]
                logger.info(f"{self.name}: IF added: {metrics['impact_factor']}")
        except Exception as e:
            logger.debug(f"{self.name}: IF lookup failed: {e}")

    def _merge_metadata_into_paper(self, paper: Paper, metadata_dict: dict) -> None:
        """Merge metadata dictionary from ScholarEngine into Paper object."""

        def update_field(section, field_name, value, engines):
            if value is None:
                return
            # Type conversions
            if section == "id" and not isinstance(value, str):
                value = str(value)
            if field_name == "year" and not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return
            if section == "citation_count" and not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return
            try:
                section_obj = getattr(paper.metadata, section)
                setattr(section_obj, field_name, value)
                setattr(section_obj, f"{field_name}_engines", engines)
            except Exception as exc:
                logger.debug(
                    f"_assign_field: failed setting {section}.{field_name} "
                    f"({type(exc).__name__}: {exc})"
                )

        # ID section
        if "id" in metadata_dict:
            id_data = metadata_dict["id"]
            for field in [
                "doi",
                "arxiv_id",
                "pmid",
                "corpus_id",
                "semantic_id",
                "ieee_id",
                "scholar_id",
            ]:
                if field in id_data:
                    update_field(
                        "id", field, id_data[field], id_data.get(f"{field}_engines", [])
                    )

        # Basic section
        if "basic" in metadata_dict:
            basic_data = metadata_dict["basic"]
            for field in ["title", "authors", "year", "abstract", "keywords", "type"]:
                if field in basic_data:
                    update_field(
                        "basic",
                        field,
                        basic_data[field],
                        basic_data.get(f"{field}_engines", []),
                    )

        # Citation count section
        if "citation_count" in metadata_dict:
            cc_data = metadata_dict["citation_count"]
            if "total" in cc_data:
                update_field(
                    "citation_count",
                    "total",
                    cc_data["total"],
                    cc_data.get("total_engines", []),
                )
            for year in range(2015, 2026):
                if str(year) in cc_data:
                    update_field(
                        "citation_count",
                        f"y{year}",
                        cc_data[str(year)],
                        cc_data.get(f"{year}_engines", []),
                    )

        # Publication section
        if "publication" in metadata_dict:
            pub_data = metadata_dict["publication"]
            for field in [
                "journal",
                "short_journal",
                "impact_factor",
                "issn",
                "volume",
                "issue",
                "first_page",
                "last_page",
                "pages",
                "publisher",
            ]:
                if field in pub_data:
                    update_field(
                        "publication",
                        field,
                        pub_data[field],
                        pub_data.get(f"{field}_engines", []),
                    )

        # URL section
        if "url" in metadata_dict:
            url_data = metadata_dict["url"]
            for field in ["doi", "publisher", "arxiv", "corpus_id"]:
                if field in url_data:
                    update_field(
                        "url",
                        field,
                        url_data[field],
                        url_data.get(f"{field}_engines", []),
                    )


# EOF
