#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the OA-sources cache, focused on THE HOT-PATH RULE.

A lookup must never crawl the OpenAlex corpus, and must never raise "event
loop is already running". Both were reproduced on a cold cache: the sync
path hung for minutes, the async path crashed instantly. These tests pin
the fix down.

No mocks (repo doctrine) and no network: the cache is pointed at a tmp dir,
the cache file is the fixture, and the crawl is a real subclass tripwire.
"""

import asyncio
import json
import time

import pytest

from scitex_scholar.core.oa_cache import OASourcesCache

OA_FIXTURE = {
    "source_names": ["plos one", "scientific reports"],
    "issns": ["1932-6203", "2045-2322"],
    "count": 2,
}


def _write_cache(cache_dir, timestamp):
    """Write a real cache file -- the fixture is data, not a mock."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {**OA_FIXTURE, "timestamp": timestamp}
    (cache_dir / "oa_sources_cache.json").write_text(json.dumps(payload))


class _NetworkGuard(OASourcesCache):
    """A cache whose corpus crawl is a tripwire, not a fetch.

    Trips on ``_fetch_oa_sources_sync`` -- the single choke point every crawl
    path goes through, old (direct call from ``ensure_loaded``) and new
    (``refresh``) alike -- so a lookup that reaches the network fails loudly
    however the crawl is wired.
    """

    def _fetch_oa_sources_sync(self, max_pages: int = 100) -> None:
        raise AssertionError(
            "A lookup reached the OA-sources crawl. That is the defect this "
            "class exists to prevent."
        )


class _StubFetch(OASourcesCache):
    """A cache whose crawl is a trivial coroutine -- no network.

    Used to exercise the sync wrapper's event-loop handling without a real
    fetch: the coroutine just records that it ran.
    """

    async def _fetch_oa_sources_async(self, max_pages: int = 100) -> None:
        self._oa_source_names = {"stub journal"}
        self._loaded = True


def test_lookup_with_fresh_cache_resolves(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = cache.is_oa_source("PLOS ONE")
    # Assert
    assert result is True


def test_lookup_with_stale_cache_still_resolves(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time() - 365 * 86400)
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = cache.is_oa_source("PLOS ONE")
    # Assert
    assert result is True


def test_stale_cache_does_not_trigger_a_crawl(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time() - 365 * 86400)
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    cache.is_oa_source("PLOS ONE")
    # Assert -- reaching the crawl would have raised from refresh()
    assert cache.source_count == 2


def test_cold_cache_lookup_returns_not_known_without_crawling(tmp_path):
    # Arrange -- empty dir: no cache file
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = cache.is_oa_source("PLOS ONE")
    # Assert -- "not known", not a minutes-long corpus crawl
    assert result is False


def test_cold_cache_lookup_inside_running_loop_does_not_raise(tmp_path):
    # Arrange -- reproduces the async-path crash: a cold lookup from inside a
    # running event loop used to raise "This event loop is already running".
    cache = _NetworkGuard(cache_dir=tmp_path)

    async def lookup_in_loop():
        return cache.is_oa_source("PLOS ONE")

    # Act
    result = asyncio.run(lookup_in_loop())
    # Assert
    assert result is False


def test_cold_cache_warns_with_an_actionable_hint(tmp_path, caplog):
    # Arrange
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    with caplog.at_level("WARNING"):
        cache.is_oa_source("PLOS ONE")
    # Assert
    assert "refresh_oa_cache" in caplog.text


def test_issn_lookup_reads_cache_without_crawling(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = cache.is_oa_issn("1932-6203")
    # Assert
    assert result is True


def test_refresh_inside_running_loop_does_not_raise_already_running(tmp_path):
    # Arrange -- the explicit refresh path must survive being called from
    # async code: the sync wrapper runs the crawl on a thread rather than
    # calling run_until_complete on the live loop.
    cache = _StubFetch(cache_dir=tmp_path)

    async def refresh_in_loop():
        cache.refresh()
        return cache.source_count

    # Act
    count = asyncio.run(refresh_in_loop())
    # Assert
    assert count == 1


def test_refresh_outside_any_loop_runs_the_crawl(tmp_path):
    # Arrange
    cache = _StubFetch(cache_dir=tmp_path)
    # Act
    cache.refresh()
    # Assert
    assert cache.source_count == 1


def test_corrupt_cache_is_treated_as_cold_not_fatal(tmp_path):
    # Arrange
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "oa_sources_cache.json").write_text("{not json")
    cache = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = cache.is_oa_source("PLOS ONE")
    # Assert
    assert result is False


# EOF
