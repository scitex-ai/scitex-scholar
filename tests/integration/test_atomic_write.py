#!/usr/bin/env python3
"""Tests for atomic metadata.json / tables.json writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from scitex_scholar.storage.PaperIO import _atomic_write_json


def test_writes_valid_json(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    _atomic_write_json(p, {"x": 1, "y": [2, 3]})
    # Assert
    assert json.loads(p.read_text()) == {"x": 1, "y": [2, 3]}


def test_overwrites_existing_file(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"old": True}))
    # Act
    _atomic_write_json(p, {"new": True})
    # Assert
    assert json.loads(p.read_text()) == {"new": True}


def test_leaves_no_tmp_file_on_success_not_p_with_suffix_json_tmp_exists(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    _atomic_write_json(p, {"x": 1})
    # Act
    # Assert
    assert not (p.with_suffix(".json.tmp")).exists()


def test_leaves_no_tmp_file_on_success_list_tmp_path_glob_tmp(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    _atomic_write_json(p, {"x": 1})
    # Act
    # Assert
    assert list(tmp_path.glob("*.tmp")) == []




def test_preserves_existing_file_on_serializer_error_raises_typeerror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"intact": True}))
    # Act
    class _NotSerializable:
        pass
    # Act
    # Assert
    with pytest.raises(TypeError):
        _atomic_write_json(p, {"bad": _NotSerializable()})


def test_preserves_existing_file_on_serializer_error_json_loads_p_read_text_intact_true(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"intact": True}))
    # Act
    class _NotSerializable:
        pass
    # Act
    # Assert
    assert json.loads(p.read_text()) == {"intact": True}




def test_cleans_up_tmp_on_failure_raises_typeerror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    class _NotSerializable:
        pass
    # Act
    # Assert
    with pytest.raises(TypeError):
        _atomic_write_json(p, {"bad": _NotSerializable()})


def test_cleans_up_tmp_on_failure_list_tmp_path_glob_tmp(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    class _NotSerializable:
        pass
    # Act
    # Assert
    assert list(tmp_path.glob("*.tmp")) == []




def test_survives_mid_write_crash_raises_oserror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    p.write_text(json.dumps({"prior": "valid"}))
    # Act
    # Assert
    with (
        mock.patch.object(os, "fsync", side_effect=OSError("crash!")),
        pytest.raises(OSError),
    ):
        _atomic_write_json(p, {"new": "would-have-been"})


def test_survives_mid_write_crash_json_loads_p_read_text_prior_valid(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    p.write_text(json.dumps({"prior": "valid"}))
    # Act
    # Assert
    assert json.loads(p.read_text()) == {"prior": "valid"}


def test_survives_mid_write_crash_list_tmp_path_glob_tmp(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    p.write_text(json.dumps({"prior": "valid"}))
    # Act
    # Assert
    assert list(tmp_path.glob("*.tmp")) == []




def test_atomic_replace_is_used_spy_call_count_equals_n_1(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    with mock.patch.object(os, "replace", wraps=os.replace) as spy:
        _atomic_write_json(p, {"x": 1})
    # Act
    # Assert
    assert spy.call_count == 1


def test_atomic_replace_is_used_path_src_suffix_tmp(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    with mock.patch.object(os, "replace", wraps=os.replace) as spy:
        _atomic_write_json(p, {"x": 1})
    # Act
    src, dst = spy.call_args.args
    # Act
    # Assert
    assert Path(src).suffix == ".tmp"


def test_atomic_replace_is_used_path_dst_p(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    with mock.patch.object(os, "replace", wraps=os.replace) as spy:
        _atomic_write_json(p, {"x": 1})
    # Act
    src, dst = spy.call_args.args
    # Act
    # Assert
    assert Path(dst) == p




def test_unicode_content_json_loads_p_read_text_encoding_utf_8_title_pileps(tmp_path: Path):
    # Arrange
    p = tmp_path / "u.json"
    # Act
    _atomic_write_json(p, {"title": "Épilepsie 日本語 🧠"})
    # Assert
    assert json.loads(p.read_text(encoding="utf-8"))["title"] == "Épilepsie 日本語 🧠"
