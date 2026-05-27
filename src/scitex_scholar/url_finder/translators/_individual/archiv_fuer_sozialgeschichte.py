#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Archiv fuer Sozialgeschichte translator."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from playwright.async_api import Page

from .._core.base import BaseTranslator


class ArchivFuerSozialgeschichteTranslator(BaseTranslator):
    """Archiv fuer Sozialgeschichte."""

    LABEL = "Archiv fuer Sozialgeschichte"
    URL_TARGET_PATTERN = r"^https?://library\.fes\.de/jportal/"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return bool(re.match(cls.URL_TARGET_PATTERN, url))

    @classmethod
    async def extract_pdf_urls_async(cls, page: Page) -> List[str]:
        return []
