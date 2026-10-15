"""Tests for the completion drop-in contract v1.

All install-behavior tests run with an isolated temp HOME so they never
touch the real ``~/.scitex`` or shell rc files. Env vars are saved and
restored with an explicit yield fixture (PA-306 forbids monkeypatch).
"""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_scholar._cli_main import cli
from scitex_scholar._cli.completion import _cache_path

PROG = "scitex-scholar"
EXPECTED_REL = Path(".scitex") / "scholar" / "runtime" / "completion" / PROG


@pytest.fixture
def isolated_home(tmp_path):
    """Point HOME at tmp_path and clear SCITEX_DIR (save/restore)."""
    previous_home = os.environ.get("HOME")
    previous_scitex_dir = os.environ.get("SCITEX_DIR")
    os.environ["HOME"] = str(tmp_path)
    os.environ.pop("SCITEX_DIR", None)
    try:
        yield tmp_path
    finally:
        if previous_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = previous_home
        if previous_scitex_dir is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = previous_scitex_dir


@pytest.fixture
def custom_scitex_dir(tmp_path):
    """Point HOME and SCITEX_DIR at fresh tmp dirs (save/restore)."""
    previous_home = os.environ.get("HOME")
    previous_scitex_dir = os.environ.get("SCITEX_DIR")
    home = tmp_path / "home"
    home.mkdir()
    scitex_dir = tmp_path / "custom-scitex"
    os.environ["HOME"] = str(home)
    os.environ["SCITEX_DIR"] = str(scitex_dir)
    try:
        yield scitex_dir
    finally:
        if previous_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = previous_home
        if previous_scitex_dir is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = previous_scitex_dir


# ---------------------------------------------------------------------------
# completion install
# ---------------------------------------------------------------------------


def test_install_exits_zero_for_default_shell(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install"])
    # Assert
    assert result.exit_code == 0


def test_install_writes_dropin_file_for_default_shell(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["completion", "install"])
    # Assert
    assert (isolated_home / EXPECTED_REL).is_file()


def test_install_prints_dropin_path_for_default_shell(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install"])
    # Assert
    assert str(isolated_home / EXPECTED_REL) in result.output


def test_install_writes_nonempty_completion_script(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["completion", "install"])
    # Assert
    assert (isolated_home / EXPECTED_REL).read_text().strip() != ""


def test_install_accepts_explicit_bash_shell_flag(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install", "--shell", "bash", "--yes"])
    # Assert
    assert result.exit_code == 0


def test_install_is_idempotent_across_repeated_runs(isolated_home):
    # Arrange
    runner = CliRunner()
    args = ["completion", "install", "--shell", "bash", "--yes"]
    # Act
    runner.invoke(cli, args)
    content_first = (isolated_home / EXPECTED_REL).read_text()
    # Act
    runner.invoke(cli, args)
    content_second = (isolated_home / EXPECTED_REL).read_text()
    # Assert
    assert content_first == content_second


def test_install_leaves_bashrc_untouched(isolated_home):
    # Arrange
    bashrc = isolated_home / ".bashrc"
    bashrc.write_text("# user bashrc\n")
    (isolated_home / ".zshrc").write_text("# user zshrc\n")
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Assert
    assert bashrc.read_text() == "# user bashrc\n"


def test_install_leaves_zshrc_untouched(isolated_home):
    # Arrange
    (isolated_home / ".bashrc").write_text("# user bashrc\n")
    zshrc = isolated_home / ".zshrc"
    zshrc.write_text("# user zshrc\n")
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Assert
    assert zshrc.read_text() == "# user zshrc\n"


def test_install_with_custom_scitex_dir_exits_zero(custom_scitex_dir):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install", "--yes"])
    # Assert
    assert result.exit_code == 0


def test_install_with_custom_scitex_dir_writes_expected_dropin(custom_scitex_dir):
    # Arrange
    runner = CliRunner()
    expected = custom_scitex_dir / "scholar" / "runtime" / "completion" / PROG
    # Act
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Assert
    assert expected.is_file()


def test_install_with_custom_scitex_dir_prints_expected_path(custom_scitex_dir):
    # Arrange
    runner = CliRunner()
    expected = custom_scitex_dir / "scholar" / "runtime" / "completion" / PROG
    # Act
    result = runner.invoke(cli, ["completion", "install", "--yes"])
    # Assert
    assert str(expected) in result.output


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_install_supports_shell_variants_with_zero_exit(isolated_home, shell):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install", "--shell", shell, "--yes"])
    # Assert
    assert result.exit_code == 0


def test_dry_run_exits_zero_without_writing(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install", "--dry-run"])
    # Assert
    assert result.exit_code == 0


def test_dry_run_writes_no_dropin_file(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["completion", "install", "--dry-run"])
    # Assert
    assert not (isolated_home / EXPECTED_REL).exists()


def test_dry_run_mentions_target_dropin_path(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "install", "--dry-run"])
    # Assert
    assert str(isolated_home / EXPECTED_REL) in result.output


# ---------------------------------------------------------------------------
# completion status
# ---------------------------------------------------------------------------


def test_status_exits_zero_before_install(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "status"])
    # Assert
    assert result.exit_code == 0


def test_status_reports_missing_before_install(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "status"])
    # Assert
    assert "Completion not installed:" in result.output


def test_status_reports_installed_after_install(isolated_home):
    # Arrange
    runner = CliRunner()
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Act
    result = runner.invoke(cli, ["completion", "status"])
    # Assert
    assert "Completion installed:" in result.output


def test_status_mentions_dropin_path_after_install(isolated_home):
    # Arrange
    runner = CliRunner()
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Act
    result = runner.invoke(cli, ["completion", "status"])
    # Assert
    assert str(isolated_home / EXPECTED_REL) in result.output


def test_status_json_exits_zero_before_install(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "status", "--json"])
    # Assert
    assert result.exit_code == 0


def test_status_json_reports_missing_before_install(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["completion", "status", "--json"])
    payload = json.loads(result.output)
    # Assert
    assert payload["installed"] is False


def test_status_json_reports_installed_after_install(isolated_home):
    # Arrange
    runner = CliRunner()
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Act
    result = runner.invoke(cli, ["completion", "status", "--json"])
    payload = json.loads(result.output)
    # Assert
    assert payload["installed"] is True


def test_status_json_carries_dropin_path_after_install(isolated_home):
    # Arrange
    runner = CliRunner()
    runner.invoke(cli, ["completion", "install", "--yes"])
    # Act
    result = runner.invoke(cli, ["completion", "status", "--json"])
    payload = json.loads(result.output)
    # Assert
    assert payload["path"] == str(isolated_home / EXPECTED_REL)


def test_cache_path_defaults_under_home_scitex_dir(isolated_home):
    # Arrange
    prog = PROG
    # Act
    cache = _cache_path(prog)
    # Assert
    assert cache == isolated_home / EXPECTED_REL


# ---------------------------------------------------------------------------
# Legacy Phase W aliases (audit §1a requires the top-level names)
# ---------------------------------------------------------------------------


def test_legacy_install_alias_exits_zero(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["install-shell-completion", "--yes"])
    # Assert
    assert result.exit_code == 0


def test_legacy_install_alias_warns_deprecation_on_stderr(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["install-shell-completion", "--yes"])
    # Assert
    assert "deprecated" in result.stderr.lower()


def test_legacy_install_alias_writes_dropin_file(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    runner.invoke(cli, ["install-shell-completion", "--yes"])
    # Assert
    assert (isolated_home / EXPECTED_REL).is_file()


def test_legacy_print_alias_exits_zero(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["print-shell-completion"])
    # Assert
    assert result.exit_code == 0


def test_legacy_print_alias_prints_nonempty_script(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["print-shell-completion"])
    # Assert
    assert result.output.strip() != ""


def test_legacy_print_alias_warns_deprecation_on_stderr(isolated_home):
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["print-shell-completion"])
    # Assert
    assert "deprecated" in result.stderr.lower()
