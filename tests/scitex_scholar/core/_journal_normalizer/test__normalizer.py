#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for JournalNormalizer, focused on THE HOT-PATH RULE.

A lookup must never crawl the OpenAlex corpus. That crawl takes minutes
(measured: 385s), so a lookup that reaches it blocks every search of the
day and then fails. These tests pin that rule down.

No mocks (repo doctrine) and no network: the normalizer is pointed at a
tmp cache dir, and the cache file itself is the fixture. The network guard
is a real subclass whose fetch path raises -- if a lookup ever reaches it,
the test fails loudly instead of quietly hanging CI for six minutes.
"""

import json
import time

import pytest

from scitex_scholar.core._journal_normalizer._normalizer import JournalNormalizer

PLOS_ONE = {
    "1932-6203": {
        "canonical_name": "PLOS ONE",
        "abbreviated_title": "PLoS ONE",
        "alternate_titles": ["Public Library of Science ONE"],
        "issns": ["1932-6203"],
        "is_oa": True,
        "publisher": "Public Library of Science",
    }
}


def _write_cache(cache_dir, timestamp):
    """Write a real cache file -- the fixture is data, not a mock."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": timestamp,
        "journal_count": len(PLOS_ONE),
        "issn_l_data": PLOS_ONE,
        "name_to_issn_l": {"plos one": "1932-6203"},
        "issn_to_issn_l": {"1932-6203": "1932-6203"},
        "abbrev_to_issn_l": {"plos one": "1932-6203"},
    }
    (cache_dir / "journal_normalizer_cache.json").write_text(json.dumps(payload))


class _NetworkGuard(JournalNormalizer):
    """A normalizer whose corpus crawl is a tripwire, not a fetch."""

    def refresh(self, max_pages: int = 500) -> None:
        raise AssertionError(
            "A lookup reached the OpenAlex corpus crawl. That is the defect "
            "this class exists to prevent."
        )


def test_lookup_with_fresh_cache_resolves_issn_l(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    issn_l = normalizer.get_issn_l("PLOS ONE")
    # Assert
    assert issn_l == "1932-6203"


def test_lookup_with_stale_cache_still_resolves(tmp_path):
    # Arrange -- a year-old cache is stale but perfectly usable
    _write_cache(tmp_path, time.time() - 365 * 86400)
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    issn_l = normalizer.get_issn_l("PLOS ONE")
    # Assert
    assert issn_l == "1932-6203"


def test_stale_cache_does_not_trigger_a_crawl(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time() - 365 * 86400)
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    normalizer.normalize("PLOS ONE")
    # Assert -- reaching the crawl would have raised from refresh()
    assert normalizer.journal_count == 1


def test_cold_cache_does_not_trigger_a_crawl(tmp_path):
    # Arrange -- empty dir: no cache file at all
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.get_issn_l("PLOS ONE")
    # Assert -- "not known", rather than a minutes-long corpus crawl
    assert result is None


def test_cold_cache_reports_journal_not_known_rather_than_open_access(tmp_path):
    # Arrange
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.is_open_access("PLOS ONE")
    # Assert -- False means "not known to be OA", the documented contract
    assert result is False


def test_cold_cache_warns_with_an_actionable_hint(tmp_path, caplog):
    # Arrange
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    with caplog.at_level("WARNING"):
        normalizer.get_issn_l("PLOS ONE")
    # Assert -- a degraded answer must name the command that fixes it
    assert "refresh_journal_cache" in caplog.text


def test_cold_cache_normalize_returns_the_original_name(tmp_path):
    # Arrange
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.normalize("J. Neurosci.")
    # Assert
    assert result == "J. Neurosci."


def test_lookup_resolves_abbreviation_to_canonical_name(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.normalize("PLoS ONE")
    # Assert
    assert result == "PLOS ONE"


def test_lookup_reports_open_access_from_cache(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.is_open_access("PLOS ONE")
    # Assert
    assert result is True


def test_ensure_loaded_without_force_refresh_does_not_crawl(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time() - 365 * 86400)
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    normalizer.ensure_loaded()
    # Assert -- a stale cache must not silently escalate to the network
    assert normalizer.journal_count == 1


def test_ensure_loaded_with_force_refresh_does_crawl(tmp_path):
    # Arrange
    _write_cache(tmp_path, time.time())
    normalizer = _NetworkGuard(cache_dir=tmp_path)

    # Act -- the explicit path is the ONLY one that may reach the crawl
    def force_refresh():
        normalizer.ensure_loaded(force_refresh=True)

    # Assert
    with pytest.raises(AssertionError):
        force_refresh()


def test_search_with_cold_cache_returns_empty_without_crawling(tmp_path):
    # Arrange
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    results = normalizer.search("neuro")
    # Assert
    assert results == []


def test_corrupt_cache_is_treated_as_cold_not_fatal(tmp_path):
    # Arrange
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "journal_normalizer_cache.json").write_text("{not json")
    normalizer = _NetworkGuard(cache_dir=tmp_path)
    # Act
    result = normalizer.get_issn_l("PLOS ONE")
    # Assert
    assert result is None


# EOF
