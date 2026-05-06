#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Timestamp: "2025-10-10 02:00:31 (ywatanabe)"
# File: /home/ywatanabe/proj/scitex_repo/src/scitex/scholar/auth/gateway/_OpenURLLinkFinder.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = "./src/scitex/scholar/auth/gateway/_OpenURLLinkFinder.py"
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

__FILE__ = __file__

import asyncio
from typing import Any, Dict, List

import scitex_logging as logging
from playwright.async_api import Page
from scitex_browser.debugging import highlight_element_async

from scitex_scholar.browser.utils import click_and_wait
from scitex_scholar.config import ScholarConfig

logger = logging.getLogger(__name__)


class OpenURLLinkFinder:
    """Finds full-text links on resolver pages by publisher name."""

    def __init__(self, config: ScholarConfig = None):
        self.name = self.__class__.__name__
        self.config = config or ScholarConfig()

    async def find_link_elements(self, page: Page, doi: str) -> List[Dict[str, Any]]:
        """Find and highlight publisher text on the page."""
        try:
            logger.info(f"{self.name}: Finding links from {page.url}")

            openurl_available_from_patterns = self.config.resolve(
                "openurl_available_from_patterns", None
            )
            if not isinstance(openurl_available_from_patterns, (list, tuple)):
                openurl_available_from_patterns = []
            seen_hrefs = set()
            found_links: List[Dict[str, Any]] = []

            for pattern in openurl_available_from_patterns:
                publisher = pattern[len("Available from ") :]
                try:
                    link_element = page.locator(f'a:has-text("{publisher}")').first
                    if await link_element.count() > 0:
                        href = await link_element.get_attribute("href")
                        if href not in seen_hrefs:
                            # logger.info(f"Found link elements for: {publisher}")
                            await highlight_element_async(link_element, 500)
                            found_links.append(
                                {
                                    "publisher": publisher,
                                    "link_element": link_element,
                                }
                            )
                            seen_hrefs.add(href)
                except Exception as e:
                    logger.debug(f"{self.name}: Could not find {publisher}: {e}")

            if found_links:
                publishers = [found_link.get("publisher") for found_link in found_links]
                logger.info(
                    f"{self.name}: Found {len(publishers)} link elements for: {', '.join(publishers)}"
                )
                return found_links

            # No publisher links found at all — capture for post-mortem.
            from scitex_browser.debugging import capture_debug_artifacts_async

            await capture_debug_artifacts_async(
                page, label=f"linkfinder_no_links_{doi[:20]}"
            )
            return []

        except Exception as e:
            from scitex_browser.debugging import capture_debug_artifacts_async

            await capture_debug_artifacts_async(
                page, label=f"linkfinder_error_{doi[:20]}"
            )
            logger.fail(f"{self.name}: Did not find any urls from {page.url}: {e}")
            return []


if __name__ == "__main__":

    async def main():
        from scitex_scholar import (
            ScholarAuthManager,
            ScholarBrowserManager,
        )

        auth_manager = ScholarAuthManager()
        browser_manager = ScholarBrowserManager(
            auth_manager=auth_manager,
            browser_mode="interactive",
            chrome_profile_name="system",
        )
        (
            browser,
            context,
        ) = await browser_manager.get_authenticated_browser_and_context_async()
        page = await context.new_page()
        url = "https://unimelb.hosted.exlibrisgroup.com/sfxlcl41?doi=10.1126/science.aao0702"
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(3000)

        finder = OpenURLLinkFinder()
        links = await finder.find_link_elements(page, "10.1126/science.aao0702")

        await click_and_wait(links[0].get("link_element"))

    asyncio.run(main())

# python -m scitex_scholar.auth.gateway._OpenURLLinkFinder

# EOF
