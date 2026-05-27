#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Primo 2018 translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class Primo2018Translator(BaseTranslator):
    """Primo 2018."""

    LABEL = "Primo 2018"
    URL_TARGET_PATTERN = r"(/primo-explore/|/(discovery|nde)/(search|fulldisplay|jsearch|dbsearch|npsearch|openurl|jfulldisplay|dbfulldisplay|npfulldisplay|collectionDiscovery)\?)"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
