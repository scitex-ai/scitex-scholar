#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLoS Journals translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class PlosJournalsTranslator(BaseTranslator):
    """PLoS Journals."""

    LABEL = "PLoS Journals"
    URL_TARGET_PATTERN = r"^https?://(www\.plos(one|ntds|compbiol|pathogens|genetics|medicine|biology)\.org|journals\.plos\.org(/\w+)?)/(search|\w+/article)"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
