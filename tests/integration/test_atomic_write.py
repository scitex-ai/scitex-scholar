#!/usr/bin/env python3
"""Tests for atomic metadata.json / tables.json writes.

The atomic-write contract is observed by behaviour, not by stubbing
`os.fsync` / `os.replace` with mock objects. Where a fault path needs
to be exercised (the mid-write crash, or asserting that ``os.replace``
was invoked), `_atomic_write_json` exposes ``fsync`` / ``replace``
kwargs and we pass real recording callables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scitex_scholar.storage.PaperIO import _atomic_write_json


class _ReplaceSpy:
    """Real ``os.replace``-shaped callable that records every call.

    Replaces the previous ``mock.patch.object(os, 'replace', wraps=os.replace)``
    spy. Behaves identically to ``os.replace`` and additionally records
    each ``(src, dst)`` pair so the test can assert the production code
    invoked it with the expected paths.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, src, dst) -> None:
        self.calls.append((str(src), str(dst)))
        os.replace(src, dst)


def _crash_fsync(fd: int) -> None:
    """Real callable substituted for ``os.fsync`` to fault-inject a crash.

    Mirrors a kernel-level fsync failure (e.g. disk-full after flush);
    `_atomic_write_json` must propagate the OSError and leave the original
    file untouched.
    """
    raise OSError("crash!")


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


def test_leaves_no_tmp_file_on_success_suffix_not_present(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    _atomic_write_json(p, {"x": 1})
    # Assert
    assert not (p.with_suffix(".json.tmp")).exists()


def test_leaves_no_tmp_file_on_success_glob_empty(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    # Act
    _atomic_write_json(p, {"x": 1})
    # Assert
    assert list(tmp_path.glob("*.tmp")) == []


def test_preserves_existing_file_on_serializer_error_raises_typeerror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"intact": True}))
    class _NotSerializable:
        pass
    # Act
    ctx = pytest.raises(TypeError)
    # Assert
    with ctx:
        _atomic_write_json(p, {"bad": _NotSerializable()})


def test_preserves_existing_file_on_serializer_error_content_unchanged(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"intact": True}))
    class _NotSerializable:
        pass
    try:
        _atomic_write_json(p, {"bad": _NotSerializable()})
    except TypeError:
        pass
    # Act
    content = json.loads(p.read_text())
    # Assert
    assert content == {"intact": True}


def test_cleans_up_tmp_on_failure_raises_typeerror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    class _NotSerializable:
        pass
    # Act
    ctx = pytest.raises(TypeError)
    # Assert
    with ctx:
        _atomic_write_json(p, {"bad": _NotSerializable()})


def test_cleans_up_tmp_on_failure_no_tmp_files_remain(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    class _NotSerializable:
        pass
    try:
        _atomic_write_json(p, {"bad": _NotSerializable()})
    except TypeError:
        pass
    # Act
    leftovers = list(tmp_path.glob("*.tmp"))
    # Assert
    assert leftovers == []


def test_survives_mid_write_crash_raises_oserror(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"prior": "valid"}))
    # Act
    ctx = pytest.raises(OSError)
    # Assert
    with ctx:
        _atomic_write_json(p, {"new": "would-have-been"}, fsync=_crash_fsync)


def test_survives_mid_write_crash_existing_content_unchanged(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"prior": "valid"}))
    try:
        _atomic_write_json(p, {"new": "would-have-been"}, fsync=_crash_fsync)
    except OSError:
        pass
    # Act
    content = json.loads(p.read_text())
    # Assert
    assert content == {"prior": "valid"}


def test_survives_mid_write_crash_no_tmp_left(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"prior": "valid"}))
    try:
        _atomic_write_json(p, {"new": "would-have-been"}, fsync=_crash_fsync)
    except OSError:
        pass
    # Act
    leftovers = list(tmp_path.glob("*.tmp"))
    # Assert
    assert leftovers == []


def test_atomic_replace_is_used_called_exactly_once(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    spy = _ReplaceSpy()
    # Act
    _atomic_write_json(p, {"x": 1}, replace=spy)
    # Assert
    assert len(spy.calls) == 1


def test_atomic_replace_is_used_src_has_tmp_suffix(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    spy = _ReplaceSpy()
    _atomic_write_json(p, {"x": 1}, replace=spy)
    # Act
    src, _dst = spy.calls[0]
    # Assert
    assert Path(src).suffix == ".tmp"


def test_atomic_replace_is_used_dst_is_target_path(tmp_path: Path):
    # Arrange
    p = tmp_path / "a.json"
    spy = _ReplaceSpy()
    _atomic_write_json(p, {"x": 1}, replace=spy)
    # Act
    _src, dst = spy.calls[0]
    # Assert
    assert Path(dst) == p


def test_unicode_content_round_trip(tmp_path: Path):
    # Arrange
    p = tmp_path / "u.json"
    # Act
    _atomic_write_json(p, {"title": "Épilepsie 日本語 🧠"})
    # Assert
    assert json.loads(p.read_text(encoding="utf-8"))["title"] == "Épilepsie 日本語 🧠"
