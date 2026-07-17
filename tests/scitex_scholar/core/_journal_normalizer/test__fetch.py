#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the OpenAlex corpus fetch module.

The crawl itself needs the network, so it is not exercised here. What IS
pinned down is the module's contract surface: the constants callers depend
on, and the fact that it advertises no bound it cannot honour.
"""

import inspect

from scitex_scholar.core._journal_normalizer import _fetch


def test_checkpoint_interval_is_positive():
    # Arrange
    interval = _fetch.CHECKPOINT_EVERY_PAGES
    # Act
    is_positive = interval > 0
    # Assert -- an interrupted crawl must be able to keep partial progress
    assert is_positive


def test_page_size_is_openalex_maximum():
    # Arrange
    per_page = _fetch.PER_PAGE
    # Act
    result = per_page
    # Assert
    assert result == 200


def test_sync_wrapper_advertises_no_unenforceable_timeout():
    # Arrange -- a `future.result(timeout=...)` here waited for the full
    # crawl anyway (shutdown(wait=True)) and only then raised, discarding
    # work that had succeeded. Regression guard: keep it gone from the CODE.
    # The docstring names it deliberately, so exclude the prose from the scan.
    fn = _fetch.fetch_journals_sync
    code = inspect.getsource(fn).replace(fn.__doc__ or "", "")
    # Act
    has_future_timeout = "future.result(timeout" in code
    # Assert
    assert not has_future_timeout


def test_fetch_async_is_a_coroutine_function():
    # Arrange
    fn = _fetch.fetch_journals_async
    # Act
    result = inspect.iscoroutinefunction(fn)
    # Assert
    assert result is True


# EOF
