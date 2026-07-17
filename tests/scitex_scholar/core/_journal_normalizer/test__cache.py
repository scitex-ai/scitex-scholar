#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for journal normalizer cache I/O and freshness.

Freshness is ADVISORY: `is_fresh` reports whether a refresh is due, and
must never be read as "this data is unusable". See the package README.
"""

import json
import time

from scitex_scholar.core._journal_normalizer._cache import (
    CACHE_TTL_SECONDS,
    cache_file,
    is_fresh,
    load_cache,
    save_cache,
)


def test_cache_file_is_named_inside_the_cache_dir(tmp_path):
    # Arrange
    cache_dir = tmp_path
    # Act
    path = cache_file(cache_dir)
    # Assert
    assert path == tmp_path / "journal_normalizer_cache.json"


def test_load_cache_returns_none_when_absent(tmp_path):
    # Arrange
    path = tmp_path / "journal_normalizer_cache.json"
    # Act
    result = load_cache(path)
    # Assert
    assert result is None


def test_load_cache_returns_none_on_corrupt_json(tmp_path):
    # Arrange
    path = tmp_path / "journal_normalizer_cache.json"
    path.write_text("{not json")
    # Act
    result = load_cache(path)
    # Assert
    assert result is None


def test_save_cache_roundtrips_payload(tmp_path):
    # Arrange
    path = tmp_path / "journal_normalizer_cache.json"
    save_cache(path, {"journal_count": 1, "issn_l_data": {"x": {}}})
    # Act
    result = load_cache(path)
    # Assert
    assert result["issn_l_data"] == {"x": {}}


def test_save_cache_stamps_a_timestamp(tmp_path):
    # Arrange
    path = tmp_path / "journal_normalizer_cache.json"
    save_cache(path, {"journal_count": 0})
    # Act
    result = json.loads(path.read_text())
    # Assert
    assert result["timestamp"] > 0


def test_save_cache_creates_missing_parent_dir(tmp_path):
    # Arrange
    path = tmp_path / "nested" / "journal_normalizer_cache.json"
    # Act
    save_cache(path, {"journal_count": 0})
    # Assert
    assert path.exists()


def test_is_fresh_true_for_recent_timestamp():
    # Arrange
    stamp = time.time()
    # Act
    result = is_fresh(stamp)
    # Assert
    assert result is True


def test_is_fresh_false_beyond_ttl():
    # Arrange
    stamp = time.time() - (CACHE_TTL_SECONDS + 60)
    # Act
    result = is_fresh(stamp)
    # Assert
    assert result is False


# EOF
