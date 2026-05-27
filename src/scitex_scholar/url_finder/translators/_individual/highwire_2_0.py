#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HighWire 2.0 translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class Highwire20Translator(BaseTranslator):
    """HighWire 2.0."""

    LABEL = "HighWire 2.0"
    URL_TARGET_PATTERN = r"^[^?#]+(/content/([0-9.]+[A-Z\-]*/|current|firstcite|early)|/search\?.*?\bsubmit=|/search(/results)?\?fulltext=|/cgi/collection/.|/search/.)"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
