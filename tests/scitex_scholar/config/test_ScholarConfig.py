#!/usr/bin/env python3
"""Leaf-owned source policy: local corpora first, online APIs last."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file()
)
_CONFIG_DIR = _REPO_ROOT / "src" / "scitex_scholar" / "config"
_CONFIGS = [
    _CONFIG_DIR / "default.yaml",
    _CONFIG_DIR / "_categories" / "search_engines.yaml",
]
_EXPECTED_TIERS = {
    "primary": ["CrossRefLocal", "OpenAlexLocal"],
    "online_fallback": ["CrossRef", "OpenAlex"],
}


@pytest.mark.parametrize("config_path", _CONFIGS, ids=lambda path: path.name)
def test_source_tiers_name_local_corpora_primary_and_online_apis_fallback(config_path):
    # Arrange
    raw = config_path.read_text()
    # Act
    config = yaml.safe_load(raw)
    # Assert
    assert config["source_tiers"] == _EXPECTED_TIERS


@pytest.mark.parametrize("config_path", _CONFIGS, ids=lambda path: path.name)
def test_primary_local_sources_precede_corresponding_online_fallbacks(config_path):
    # Arrange
    engines = yaml.safe_load(config_path.read_text())["engines"]
    # Act
    ordered = [engines.index(name) for name in ["CrossRefLocal", "OpenAlexLocal", "CrossRef", "OpenAlex"]]
    # Assert
    assert ordered == sorted(ordered)
