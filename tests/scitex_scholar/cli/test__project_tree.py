#!/usr/bin/env python3
"""Tests for `scitex scholar link-project-tree`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_scholar.cli._project_tree import (
    _home_library,
    link_project_tree,
)


def test_creates_symlink_link_is_symlink(tmp_path: Path):
    # Arrange
    # Act
    link = link_project_tree(tmp_path)
    # Act
    # Assert
    assert link.is_symlink()


def test_creates_symlink_link_readlink_home_library(tmp_path: Path):
    # Arrange
    # Act
    link = link_project_tree(tmp_path)
    # Act
    # Assert
    assert link.readlink() == _home_library()


def test_creates_symlink_link_equals_tmp_path_scitex_scholar_librar(tmp_path: Path):
    # Arrange
    # Act
    link = link_project_tree(tmp_path)
    # Act
    # Assert
    assert link == tmp_path / ".scitex" / "scholar" / "library"




def test_idempotent_first_equals_second(tmp_path: Path):
    # Arrange
    first = link_project_tree(tmp_path)
    # Act
    second = link_project_tree(tmp_path)
    # Act
    # Assert
    assert first == second


def test_idempotent_second_readlink_home_library(tmp_path: Path):
    # Arrange
    first = link_project_tree(tmp_path)
    # Act
    second = link_project_tree(tmp_path)
    # Act
    # Assert
    assert second.readlink() == _home_library()




def test_differing_symlink_without_force_raises(tmp_path: Path):
    # Arrange
    link_parent = tmp_path / ".scitex" / "scholar"
    link_parent.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    # Act
    (link_parent / "library").symlink_to(other)

    # Assert
    with pytest.raises(FileExistsError):
        link_project_tree(tmp_path)


def test_differing_symlink_with_force_replaces(tmp_path: Path):
    # Arrange
    link_parent = tmp_path / ".scitex" / "scholar"
    link_parent.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (link_parent / "library").symlink_to(other)

    # Act
    link = link_project_tree(tmp_path, force=True)
    # Assert
    assert link.readlink() == _home_library()


def test_real_dir_without_force_raises(tmp_path: Path):
    # Arrange
    link_path = tmp_path / ".scitex" / "scholar" / "library"
    # Act
    link_path.mkdir(parents=True)

    # Assert
    with pytest.raises(FileExistsError):
        link_project_tree(tmp_path)


def test_real_dir_with_force_replaces_link_is_symlink(tmp_path: Path):
    # Arrange
    link_path = tmp_path / ".scitex" / "scholar" / "library"
    link_path.mkdir(parents=True)
    (link_path / "sentinel").write_text("x")
    # Act
    link = link_project_tree(tmp_path, force=True)
    # Act
    # Assert
    assert link.is_symlink()


def test_real_dir_with_force_replaces_not_link_path_sentinel_exists_or_link_readlink_home_library(tmp_path: Path):
    # Arrange
    link_path = tmp_path / ".scitex" / "scholar" / "library"
    link_path.mkdir(parents=True)
    (link_path / "sentinel").write_text("x")
    # Act
    link = link_project_tree(tmp_path, force=True)
    # Act
    # Assert
    assert not (link_path / "sentinel").exists() or link.readlink() == _home_library()




def test_project_dir_missing_raises(tmp_path: Path):
    # Arrange
    # Act
    # Assert
    with pytest.raises(FileNotFoundError):
        link_project_tree(tmp_path / "does-not-exist")
