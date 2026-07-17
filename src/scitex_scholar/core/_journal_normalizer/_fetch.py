#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bulk journal fetching from OpenAlex.

This is a CORPUS CRAWL: it walks the whole OpenAlex journal list and takes
minutes. It must only ever be reached from an EXPLICIT refresh, never from
a lookup -- see this package's README.

Two properties this module owes its callers:
  - It never claims a bound it cannot honour (a running thread cannot be
    cancelled, so a "timeout" that still waits for the thread is a lie).
  - It checkpoints, so an interrupted crawl keeps the pages it paid for.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, Optional

import aiohttp
import scitex_logging as logging

logger = logging.getLogger(__name__)

OPENALEX_SOURCES_URL = "https://api.openalex.org/sources"
OPENALEX_POLITE_EMAIL = "research@scitex.io"

PER_PAGE = 200
SELECT_FIELDS = (
    "display_name,issn_l,issn,abbreviated_title,alternate_titles,"
    "is_oa,host_organization_name"
)
CHECKPOINT_EVERY_PAGES = 25


async def fetch_journals_async(
    add_source: Callable[[Dict], None],
    checkpoint: Optional[Callable[[], None]] = None,
    max_pages: int = 500,
    filter_oa_only: bool = False,
) -> int:
    """Walk the OpenAlex sources list, handing each source to `add_source`.

    Args:
        add_source: Called once per source record.
        checkpoint: Called periodically so partial progress can be
            persisted. An interrupted crawl must not throw away the pages
            it already fetched.
        max_pages: Page cap (PER_PAGE records per page).
        filter_oa_only: Restrict to open-access sources.

    Returns:
        Number of pages fetched.
    """
    cursor = "*"
    pages_fetched = 0
    filter_param = "is_oa:true" if filter_oa_only else "type:journal"

    async with aiohttp.ClientSession() as session:
        while pages_fetched < max_pages:
            url = (
                f"{OPENALEX_SOURCES_URL}"
                f"?filter={filter_param}"
                f"&per_page={PER_PAGE}"
                f"&cursor={cursor}"
                f"&mailto={OPENALEX_POLITE_EMAIL}"
                f"&select={SELECT_FIELDS}"
            )

            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"OpenAlex API returned {resp.status}")
                        break

                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        break

                    for source in results:
                        add_source(source)

                    meta = data.get("meta", {})
                    next_cursor = meta.get("next_cursor")
                    if not next_cursor or next_cursor == cursor:
                        break
                    cursor = next_cursor
                    pages_fetched += 1

                    if checkpoint and pages_fetched % CHECKPOINT_EVERY_PAGES == 0:
                        checkpoint()
                        logger.info(f"Fetched {pages_fetched} pages (checkpointed)")

            except asyncio.TimeoutError:
                logger.warning("OpenAlex API timeout -- keeping pages fetched so far")
                break
            except Exception as e:
                logger.error(f"Error fetching journals: {e}")
                break

    return pages_fetched


def fetch_journals_sync(
    add_source: Callable[[Dict], None],
    checkpoint: Optional[Callable[[], None]] = None,
    max_pages: int = 500,
    filter_oa_only: bool = False,
) -> int:
    """Blocking wrapper around :func:`fetch_journals_async`.

    This BLOCKS for as long as the crawl takes (minutes), by design and by
    honesty: there is no bound to advertise, because a `concurrent.futures`
    worker cannot be cancelled once running. An earlier version passed
    `future.result(timeout=120)` while the enclosing `with ThreadPoolExecutor()`
    called `shutdown(wait=True)` on exit -- so it waited for the full crawl
    anyway and only then raised TimeoutError, discarding work that had
    succeeded (measured: raised after 385s against a 120s "timeout", having
    already written a complete 24MB cache). Do not reintroduce a bound here
    that the runtime cannot enforce; keep the crawl off the hot path instead.
    """
    coro = fetch_journals_async(add_source, checkpoint, max_pages, filter_oa_only)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: safe to drive the coroutine directly.
        return asyncio.run(coro)

    # Already inside an event loop: run the crawl on its own loop in a
    # dedicated thread, and join it. Joining is explicit, not disguised.
    import threading

    result: Dict[str, int] = {"pages": 0}
    error: Dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["pages"] = asyncio.run(coro)
        except BaseException as e:  # surfaced to the caller below
            error["err"] = e

    thread = threading.Thread(target=_runner, name="journal-corpus-refresh")
    thread.start()
    thread.join()

    if "err" in error:
        raise error["err"]
    return result["pages"]


# EOF
