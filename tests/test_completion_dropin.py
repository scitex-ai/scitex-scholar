"""Tests for the completion drop-in contract v1.

All install-behavior tests run with an isolated temp HOME so they never
touch the real ``~/.scitex`` or shell rc files.
"""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_scholar._cli_main import cli
from scitex_scholar._cli.completion import _cache_path

PROG = "scitex-scholar"
EXPECTED_REL = Path(".scitex") / "scholar" / "runtime" / "completion" / PROG


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point HOME at tmp_path and clear SCITEX_DIR."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SCITEX_DIR", raising=False)
    return tmp_path


@pytest.fixture
def runner():
    """Return a Click CLI runner."""
    return CliRunner()


class TestCompletionInstall:
    """Test `completion install` writes the drop-in file."""

    def test_install_writes_dropin_and_prints_path(self, runner, isolated_home):
        # Arrange
        args = ["completion", "install", "--shell", "bash", "--yes"]
        # Act
        result = runner.invoke(cli, args)
        # Assert
        assert result.exit_code == 0
        expected = isolated_home / EXPECTED_REL
        assert expected.is_file()
        assert str(expected) in result.output
        assert expected.read_text().strip() != ""

    def test_install_default_shell_needs_no_flags(self, runner, isolated_home):
        # Arrange
        args = ["completion", "install"]
        # Act
        result = runner.invoke(cli, args)
        # Assert
        assert result.exit_code == 0
        assert (isolated_home / EXPECTED_REL).is_file()

    def test_install_is_idempotent(self, runner, isolated_home):
        # Arrange
        args = ["completion", "install", "--shell", "bash", "--yes"]
        # Act
        first = runner.invoke(cli, args)
        content_first = (isolated_home / EXPECTED_REL).read_text()
        second = runner.invoke(cli, args)
        content_second = (isolated_home / EXPECTED_REL).read_text()
        # Assert
        assert first.exit_code == 0
        assert second.exit_code == 0
        assert content_first == content_second

    def test_install_does_not_touch_shell_rc(self, runner, isolated_home):
        # Arrange
        bashrc = isolated_home / ".bashrc"
        zshrc = isolated_home / ".zshrc"
        bashrc.write_text("# user bashrc\n")
        zshrc.write_text("# user zshrc\n")
        # Act
        result = runner.invoke(cli, ["completion", "install", "--yes"])
        # Assert
        assert result.exit_code == 0
        assert bashrc.read_text() == "# user bashrc\n"
        assert zshrc.read_text() == "# user zshrc\n"

    def test_install_honors_scitex_dir(self, runner, tmp_path, monkeypatch):
        # Arrange
        home = tmp_path / "home"
        home.mkdir()
        scitex_dir = tmp_path / "custom-scitex"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SCITEX_DIR", str(scitex_dir))
        # Act
        result = runner.invoke(cli, ["completion", "install", "--yes"])
        # Assert
        assert result.exit_code == 0
        expected = scitex_dir / "scholar" / "runtime" / "completion" / PROG
        assert expected.is_file()
        assert str(expected) in result.output

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_install_all_shells(self, runner, isolated_home, shell):
        # Arrange
        args = ["completion", "install", "--shell", shell, "--yes"]
        # Act
        result = runner.invoke(cli, args)
        # Assert
        assert result.exit_code == 0
        assert (isolated_home / EXPECTED_REL).is_file()

    def test_install_dry_run_writes_nothing(self, runner, isolated_home):
        # Arrange
        args = ["completion", "install", "--dry-run"]
        # Act
        result = runner.invoke(cli, args)
        # Assert
        assert result.exit_code == 0
        assert not (isolated_home / EXPECTED_REL).exists()


class TestCompletionStatus:
    """Test `completion status` checks the drop-in file."""

    def test_status_reports_missing_before_install(self, runner, isolated_home):
        # Arrange
        args = ["completion", "status"]
        # Act
        result = runner.invoke(cli, args)
        # Assert
        assert result.exit_code == 0
        assert "not installed" in result.output.lower()
        assert str(isolated_home / EXPECTED_REL) in result.output

    def test_status_reports_installed_after_install(self, runner, isolated_home):
        # Arrange
        runner.invoke(cli, ["completion", "install", "--yes"])
        # Act
        result = runner.invoke(cli, ["completion", "status"])
        # Assert
        assert result.exit_code == 0
        assert "installed" in result.output.lower()
        assert str(isolated_home / EXPECTED_REL) in result.output

    def test_cache_path_convention(self, isolated_home, monkeypatch):
        # Arrange
        monkeypatch.setenv("HOME", str(isolated_home))
        monkeypatch.delenv("SCITEX_DIR", raising=False)
        # Act
        cache = _cache_path(PROG)
        # Assert
        assert cache == isolated_home / EXPECTED_REL
        assert os.environ.get("SCITEX_DIR", str(isolated_home / ".scitex")) is not None
