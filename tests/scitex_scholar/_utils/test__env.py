#!/usr/bin/env python3
"""Tests for the prefixed env-var resolver.

Mirrors `src/scitex_scholar/_utils/_env.py`.

The behaviour under test is a migration contract, so the important cases
are the boring ones: the documented name must WIN, the legacy name must
still WORK, and using the legacy name must be AUDIBLE. A silent fallback
would leave the user believing the documented name is what they are using.

These tests set REAL entries in `os.environ` and restore the prior state on
teardown -- `resolve_env` reads the real environment in production, so the
test drives the real environment here too.
"""

from __future__ import annotations

import logging
import os

import pytest

from scitex_scholar._utils import _env
from scitex_scholar._utils._env import resolve_env

CANONICAL = "SCITEX_SCHOLAR_TEST_VALUE"
LEGACY = "SCHOLAR_TEST_VALUE_LEGACY"
LEGACY_OLDER = "SCHOLAR_TEST_VALUE_LEGACY_OLDER"


@pytest.fixture
def env():
    """Set/unset real env vars, restoring whatever was there before.

    Also clears the resolver's once-per-process warning registry, so each
    test observes the first-use warning rather than a neighbour's leftover.
    """
    saved = {name: os.environ.get(name) for name in (CANONICAL, LEGACY, LEGACY_OLDER)}
    for name in saved:
        os.environ.pop(name, None)
    _env._warned.clear()

    yield os.environ

    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    _env._warned.clear()


def test_returns_canonical_value_when_only_canonical_is_set(env):
    """The documented name works. This is the case that was broken."""
    # Arrange
    env[CANONICAL] = "from-canonical"

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert resolved == "from-canonical"


def test_returns_legacy_value_when_only_legacy_is_set(env):
    """An existing deployment on the old spelling keeps working."""
    # Arrange
    env[LEGACY] = "from-legacy"

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert resolved == "from-legacy"


def test_canonical_wins_when_both_are_set(env):
    """Precedence is not arbitrary: the documented name must be the one that wins."""
    # Arrange
    env[CANONICAL] = "from-canonical"
    env[LEGACY] = "from-legacy"

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert resolved == "from-canonical"


def test_returns_default_when_neither_is_set(env):
    """An unset variable yields the caller's default, not an empty string."""
    # Arrange
    default = "fallback-default"

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY, default=default)

    # Assert
    assert resolved == default


def test_returns_none_when_neither_is_set_and_no_default(env):
    """Absent means None -- distinguishable from an empty configured value."""
    # Arrange
    expected = None

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert resolved is expected


def test_empty_canonical_value_is_honoured_not_treated_as_unset(env):
    """An explicitly empty value is a decision; it must not silently fall through."""
    # Arrange
    env[CANONICAL] = ""
    env[LEGACY] = "from-legacy"

    # Act
    resolved = resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert resolved == ""


def test_legacy_read_warns(env, caplog):
    """The fallback is loud -- a silent one is the bug in a new place."""
    # Arrange
    env[LEGACY] = "from-legacy"

    # Act
    with caplog.at_level(logging.WARNING):
        resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert LEGACY in caplog.text


def test_legacy_warning_names_the_replacement(env, caplog):
    """The warning is actionable: it says which name to set instead."""
    # Arrange
    env[LEGACY] = "from-legacy"

    # Act
    with caplog.at_level(logging.WARNING):
        resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert CANONICAL in caplog.text


def test_canonical_read_does_not_warn(env, caplog):
    """Doing it the documented way must be quiet."""
    # Arrange
    env[CANONICAL] = "from-canonical"

    # Act
    with caplog.at_level(logging.WARNING):
        resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert caplog.text == ""


def test_legacy_warning_is_emitted_once_per_variable(env, caplog):
    """Repeated reads must not flood the log -- once is a notice, fifty is noise."""
    # Arrange
    env[LEGACY] = "from-legacy"

    # Act
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            resolve_env(CANONICAL, legacy=LEGACY)

    # Assert
    assert caplog.text.count(CANONICAL) == 1


def test_no_legacy_argument_reads_only_the_canonical_name(env):
    """A variable with no legacy spelling must not pick up a bare-named one."""
    # Arrange
    env[LEGACY] = "from-legacy"

    # Act
    resolved = resolve_env(CANONICAL)

    # Assert
    assert resolved is None


# --- several legacy spellings, in precedence order -------------------------


def test_sequence_of_legacies_reads_the_first_one_set(env):
    """With two old spellings, the earlier one in the sequence wins."""
    # Arrange
    env[LEGACY] = "from-legacy"
    env[LEGACY_OLDER] = "from-older"

    # Act
    resolved = resolve_env(CANONICAL, legacy=(LEGACY, LEGACY_OLDER))

    # Assert
    assert resolved == "from-legacy"


def test_sequence_of_legacies_falls_through_to_a_later_one(env):
    """An older spelling still works when the newer old spelling is unset."""
    # Arrange
    env[LEGACY_OLDER] = "from-older"

    # Act
    resolved = resolve_env(CANONICAL, legacy=(LEGACY, LEGACY_OLDER))

    # Assert
    assert resolved == "from-older"


def test_canonical_wins_over_every_legacy_in_the_sequence(env):
    """The documented name beats all old spellings, not only the first."""
    # Arrange
    env[CANONICAL] = "from-canonical"
    env[LEGACY] = "from-legacy"
    env[LEGACY_OLDER] = "from-older"

    # Act
    resolved = resolve_env(CANONICAL, legacy=(LEGACY, LEGACY_OLDER))

    # Assert
    assert resolved == "from-canonical"


def test_sequence_legacy_warning_names_the_spelling_actually_used(env, caplog):
    """The warning must name the old spelling that was read, not a sibling."""
    # Arrange
    env[LEGACY_OLDER] = "from-older"

    # Act
    with caplog.at_level(logging.WARNING):
        resolve_env(CANONICAL, legacy=(LEGACY, LEGACY_OLDER))

    # Assert
    assert LEGACY_OLDER in caplog.text


# EOF
