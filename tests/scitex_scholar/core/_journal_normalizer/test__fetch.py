#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the OpenAlex corpus fetch module.

The crawl itself needs the network, so it is not exercised here. What IS
pinned down is the module's contract surface: the constants callers depend
on, and the fact that it advertises no bound it cannot honour.
"""

import ast
import inspect
import textwrap

from scitex_scholar.core._journal_normalizer import _fetch


def _code_without_docstring(fn) -> str:
    """Return a function's executable code, docstring excluded.

    Parsed via ast rather than string-replacing `fn.__doc__` out of the
    source: Python 3.13 dedents docstrings at compile time, so `__doc__`
    no longer matches the indented text `getsource` returns and the
    replace silently does nothing.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    body = tree.body[0].body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return "\n".join(ast.unparse(node) for node in body)


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
    # The docstring names it deliberately, so scan code only.
    code = _code_without_docstring(_fetch.fetch_journals_sync)
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
