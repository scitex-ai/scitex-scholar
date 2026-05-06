#!/usr/bin/env python3
"""Tests for `scitex scholar link-project-tree`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_scholar.cli._project_tree import (
    _home_library,
    link_project_tree,
)


def test_creates_symlink(tmp_path: Path):
    link = link_project_tree(tmp_path)
    assert link.is_symlink()
    assert link.readlink() == _home_library()
    assert link == tmp_path / ".scitex" / "scholar" / "library"


def test_idempotent(tmp_path: Path):
    first = link_project_tree(tmp_path)
    second = link_project_tree(tmp_path)
    assert first == second
    assert second.readlink() == _home_library()


def test_differing_symlink_without_force_raises(tmp_path: Path):
    link_parent = tmp_path / ".scitex" / "scholar"
    link_parent.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (link_parent / "library").symlink_to(other)

    with pytest.raises(FileExistsError):
        link_project_tree(tmp_path)


def test_differing_symlink_with_force_replaces(tmp_path: Path):
    link_parent = tmp_path / ".scitex" / "scholar"
    link_parent.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (link_parent / "library").symlink_to(other)

    link = link_project_tree(tmp_path, force=True)
    assert link.readlink() == _home_library()


def test_real_dir_without_force_raises(tmp_path: Path):
    link_path = tmp_path / ".scitex" / "scholar" / "library"
    link_path.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        link_project_tree(tmp_path)


def test_real_dir_with_force_replaces(tmp_path: Path):
    link_path = tmp_path / ".scitex" / "scholar" / "library"
    link_path.mkdir(parents=True)
    (link_path / "sentinel").write_text("x")

    link = link_project_tree(tmp_path, force=True)
    assert link.is_symlink()
    assert not (link_path / "sentinel").exists() or link.readlink() == _home_library()


def test_project_dir_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        link_project_tree(tmp_path / "does-not-exist")
