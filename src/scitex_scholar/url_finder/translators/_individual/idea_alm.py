#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IDEA ALM translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class IdeaAlmTranslator(BaseTranslator):
    """IDEA ALM."""

    LABEL = "IDEA ALM"
    URL_TARGET_PATTERN = r"/((notebook(_f?ext)?)|list)\.asp"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
