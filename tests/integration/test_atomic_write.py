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
    p = tmp_path / "a.json"
    _atomic_write_json(p, {"x": 1, "y": [2, 3]})
    assert json.loads(p.read_text()) == {"x": 1, "y": [2, 3]}


def test_overwrites_existing_file(tmp_path: Path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"old": True}))
    _atomic_write_json(p, {"new": True})
    assert json.loads(p.read_text()) == {"new": True}


def test_leaves_no_tmp_file_on_success(tmp_path: Path):
    p = tmp_path / "a.json"
    _atomic_write_json(p, {"x": 1})
    assert not (p.with_suffix(".json.tmp")).exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_preserves_existing_file_on_serializer_error(tmp_path: Path):
    """If json.dump raises (e.g. non-serializable object), the old file
    must stay intact and no partially-written file should replace it."""
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"intact": True}))

    class _NotSerializable:
        pass

    with pytest.raises(TypeError):
        _atomic_write_json(p, {"bad": _NotSerializable()})

    # Old contents preserved exactly.
    assert json.loads(p.read_text()) == {"intact": True}


def test_cleans_up_tmp_on_failure(tmp_path: Path):
    p = tmp_path / "a.json"

    class _NotSerializable:
        pass

    with pytest.raises(TypeError):
        _atomic_write_json(p, {"bad": _NotSerializable()})

    # No .tmp stragglers left behind.
    assert list(tmp_path.glob("*.tmp")) == []


def test_survives_mid_write_crash(tmp_path: Path):
    """Simulate the failure that produced the 3DD203D4 bug: process killed
    after write started but before file was fully flushed. With atomic
    writes, the target path must never contain a truncated file — either
    the prior valid JSON or nothing at all."""
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"prior": "valid"}))

    # Patch os.fsync to raise, simulating crash between write and replace.
    with (
        mock.patch.object(os, "fsync", side_effect=OSError("crash!")),
        pytest.raises(OSError),
    ):
        _atomic_write_json(p, {"new": "would-have-been"})

    # Target file untouched.
    assert json.loads(p.read_text()) == {"prior": "valid"}
    # No truncated .tmp left around.
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_replace_is_used(tmp_path: Path):
    """Verify the implementation actually calls os.replace (not a plain
    rename loop), guaranteeing POSIX atomic-swap semantics."""
    p = tmp_path / "a.json"
    with mock.patch.object(os, "replace", wraps=os.replace) as spy:
        _atomic_write_json(p, {"x": 1})
    assert spy.call_count == 1
    src, dst = spy.call_args.args
    assert Path(src).suffix == ".tmp"
    assert Path(dst) == p


def test_unicode_content(tmp_path: Path):
    p = tmp_path / "u.json"
    _atomic_write_json(p, {"title": "Épilepsie 日本語 🧠"})
    assert json.loads(p.read_text(encoding="utf-8"))["title"] == "Épilepsie 日本語 🧠"
