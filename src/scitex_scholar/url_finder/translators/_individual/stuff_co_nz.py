#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stuff.co.nz translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class StuffCoNzTranslator(BaseTranslator):
    """Stuff.co.nz."""

    LABEL = "Stuff.co.nz"
    URL_TARGET_PATTERN = r"^https?://(www\.)?stuff\.co\.nz/"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
