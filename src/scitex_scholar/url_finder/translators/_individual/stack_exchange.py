#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stack Exchange translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class StackExchangeTranslator(BaseTranslator):
    """Stack Exchange."""

    LABEL = "Stack Exchange"
    URL_TARGET_PATTERN = r"^https://([^/]+\.)?(((stack(overflow|exchange)|serverfault|askubuntu|superuser|stackapps)\.com)|mathoverflow\.net)/"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
