#!/usr/bin/env python3
"""Tests for the shared Click scaffolding.

Mirrors `src/scitex_scholar/_cli/_scaffolding.py`.

The load-bearing test here is `test_group_module_imports_on_cold_interpreter`,
and it MUST run in a fresh subprocess. The bug it guards -- every
`_cli.<group>` module importing `_cli_main`, which imports all of them back
at its bottom -- is invisible in-process, because by the time any test runs
`_cli_main` is already in `sys.modules` and the partially-initialized module
never appears. An in-process assertion would pass against the broken tree,
which makes it a gate that cannot fail.

Positive control, measured 2026-08-18 on the pre-fix tree: all nine group
modules raised `ImportError: cannot import name '<group>' from partially
initialized module 'scitex_scholar._cli.<group>' (most likely due to a
circular import)`. Post-fix: all nine import cleanly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from scitex_scholar._cli import _scaffolding

GROUP_MODULES = [
    "aliases",
    "auth",
    "bibtex",
    "gui",
    "library",
    "mcp",
    "paper",
    "pdf",
    "skills",
]

RE_EXPORTED_NAMES = [
    "CONTEXT_SETTINGS",
    "_CategorizedGroup",
    "_INT_OR_HELP",
    "_warn_deprecated",
]


@pytest.fixture
def categorized_group():
    """A `_CategorizedGroup` with one sectioned, one stray and one hidden command."""

    class _Group(_scaffolding._CategorizedGroup):
        SECTIONS = [("Workflow", ["listed"])]

    group = _Group(name="root")
    group.add_command(click.Command("listed", short_help="in a section"))
    group.add_command(click.Command("stray", short_help="not in a section"))
    group.add_command(click.Command("secret", short_help="hidden", hidden=True))
    return group


@pytest.fixture
def group_help_text(categorized_group):
    """Rendered `--help` output of `categorized_group`."""
    return categorized_group.get_help(click.Context(categorized_group, info_name="root"))


@pytest.fixture
def batch_size_command():
    """A command whose value-taking option uses the `_INT_OR_HELP` type."""

    @click.command(context_settings=_scaffolding.CONTEXT_SETTINGS)
    @click.option("--batch-size", type=_scaffolding._INT_OR_HELP, default=1)
    def _cmd(batch_size):  # pragma: no cover - the help path exits first
        click.echo(batch_size)

    return _cmd


@pytest.mark.parametrize("module_name", GROUP_MODULES)
def test_group_module_imports_on_cold_interpreter(module_name):
    """Importing a group module FIRST must not need `_cli_main` loaded already."""
    # Arrange
    statement = f"import scitex_scholar._cli.{module_name}"

    # Act
    result = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Assert
    assert result.returncode == 0, (
        f"cold `{statement}` failed -- the scaffolding cycle is back. Group "
        f"modules must import from `._scaffolding`, never from "
        f"`.._cli_main`.\n{result.stderr}"
    )


def test_scaffolding_does_not_import_cli_main():
    """The one-way dependency is the fix; assert it on the import graph.

    Asserting on the source rather than on an outcome: a cold import that
    happens to succeed cannot distinguish a fixed tree from a lucky one.
    """
    # Arrange
    source = Path(_scaffolding.__file__).read_text()

    # Act
    offenders = [
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "_cli_main" in line
    ]

    # Assert
    assert not offenders, (
        f"_scaffolding must not import _cli_main -- that recreates the cycle "
        f"it exists to break: {offenders}"
    )


@pytest.mark.parametrize("name", RE_EXPORTED_NAMES)
def test_cli_main_re_exports_scaffolding_names(name):
    """`from .._cli_main import <name>` stays valid for existing callers."""
    # Arrange
    from scitex_scholar import _cli_main

    # Act
    re_exported = getattr(_cli_main, name)

    # Assert
    assert re_exported is getattr(_scaffolding, name)


def test_context_settings_enables_short_help_flag():
    """`-h` is accepted as well as `--help`."""
    # Arrange
    settings = _scaffolding.CONTEXT_SETTINGS

    # Act
    help_option_names = settings["help_option_names"]

    # Assert
    assert help_option_names == ["-h", "--help"]


def test_int_or_help_converts_integers():
    """A plain numeric token converts to `int`."""
    # Arrange
    param_type = _scaffolding._INT_OR_HELP

    # Act
    converted = param_type.convert("7", None, None)

    # Assert
    assert converted == 7


def test_int_or_help_rejects_non_integers():
    """A non-numeric token fails as a usage error, not a `ValueError`."""
    # Arrange
    param_type = _scaffolding._INT_OR_HELP

    # Act
    convert_a_word = lambda: param_type.convert("seven", None, None)  # noqa: E731

    # Assert
    with pytest.raises(click.exceptions.UsageError):
        convert_a_word()


def test_int_or_help_exits_cleanly_on_help_token(batch_size_command):
    """`--batch-size -h` must print help and exit 0, not fail integer parsing."""
    # Arrange
    runner = CliRunner()

    # Act
    result = runner.invoke(batch_size_command, ["--batch-size", "-h"])

    # Assert
    assert result.exit_code == 0


def test_int_or_help_prints_help_on_help_token(batch_size_command):
    """The help text, not an integer-parse error, reaches the user."""
    # Arrange
    runner = CliRunner()

    # Act
    result = runner.invoke(batch_size_command, ["--batch-size", "-h"])

    # Assert
    assert "--batch-size" in result.output


def test_categorized_group_renders_declared_section(group_help_text):
    """A command listed in `SECTIONS` appears under its section label."""
    # Arrange
    label = "[Workflow]"

    # Act
    rendered = group_help_text

    # Assert
    assert label in rendered


def test_categorized_group_renders_unlisted_command_under_other(group_help_text):
    """A command in no section lands under `[Other]`."""
    # Arrange
    label = "[Other]"

    # Act
    rendered = group_help_text

    # Assert
    assert label in rendered


def test_categorized_group_lists_unsectioned_command_name(group_help_text):
    """The unsectioned command is not dropped from `--help`."""
    # Arrange
    name = "stray"

    # Act
    rendered = group_help_text

    # Assert
    assert name in rendered


def test_categorized_group_omits_hidden_command(group_help_text):
    """A hidden command stays out of `--help` entirely."""
    # Arrange
    name = "secret"

    # Act
    rendered = group_help_text

    # Assert
    assert name not in rendered


def test_warn_deprecated_names_the_old_form(capsys):
    """The warning names the deprecated form the user typed."""
    # Arrange
    old_form = "old-form"

    # Act
    _scaffolding._warn_deprecated(old_form, "new-form")

    # Assert
    assert old_form in capsys.readouterr().err


def test_warn_deprecated_names_the_replacement_form(capsys):
    """The warning is actionable: it names what to use instead."""
    # Arrange
    new_form = "new-form"

    # Act
    _scaffolding._warn_deprecated("old-form", new_form)

    # Assert
    assert new_form in capsys.readouterr().err


def test_warn_deprecated_writes_nothing_to_stdout(capsys):
    """Piped stdout stays clean -- the warning belongs on stderr."""
    # Arrange
    captured_stream = "out"

    # Act
    _scaffolding._warn_deprecated("old-form", "new-form")

    # Assert
    assert getattr(capsys.readouterr(), captured_stream) == ""


def test_warn_deprecated_emits_a_single_line(capsys):
    """One line, so it cannot bury the command's real output."""
    # Arrange
    expected_lines = 1

    # Act
    _scaffolding._warn_deprecated("old-form", "new-form")

    # Assert
    assert capsys.readouterr().err.count("\n") == expected_lines


# EOF
