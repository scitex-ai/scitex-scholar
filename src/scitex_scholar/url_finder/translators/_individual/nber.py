#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""National Bureau of Economic Research translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class NBERTranslator(BaseTranslator):
    """National Bureau of Economic Research."""

    LABEL = "National Bureau of Economic Research"
    URL_TARGET_PATTERN = r"^https?://(papers\.|www2?\\.)?nber\.org/(system/files/)?(papers|s|new|custom|books-and-chapters|chapters)"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
